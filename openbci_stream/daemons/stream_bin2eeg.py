"""
=============
Binary to EEG
=============

A transformer for Kafka that reads binary data and stream EEG data.

Binary -> Kafka-Transformer -> EEG

For examples and descriptions refers to documentation:
`Data storage handler <../A1-raw_cleaning.ipynb>`_
"""

import sys
import pickle
import struct
from functools import cached_property
import numpy as np
from datetime import datetime
import rawutil
import logging

from kafka import KafkaConsumer, KafkaProducer
from typing import TypeVar, Dict, Tuple, Any

# from openbci_stream.utils import autokill_process
# autokill_process(name='binary_2_eeg')

DEBUG = ('--debug' in sys.argv)

if DEBUG:
    logging.getLogger().setLevel(logging.DEBUG)
    # logging.getLogger('kafka').setLevel(logging.WARNING)


KafkaStream = TypeVar('kafka-stream')


########################################################################
class BinaryToEEG:
    """Kafka transformer with parallel implementation for processing binary raw
    data into EEG microvolts. This script requires the Kafka daemon running and
    enables an `auto-kill process <openbci_stream.utils.pid_admin.rst#module-openbci_stream.utils.pid_admin>`_
    """

    BIN_HEADER = 0xa0
    LAST_AUX_SHAPE = 0

    # ----------------------------------------------------------------------
    def __init__(self, board_id: str = ''):
        """"""
        self.board_id = board_id

        self.consumer_binary = KafkaConsumer(bootstrap_servers=['localhost:9092'],
                                             value_deserializer=pickle.loads,
                                             auto_offset_reset='latest',
                                             )
        self.consumer_binary.subscribe([f'binary{self.board_id}'])

        self.producer_eeg = KafkaProducer(bootstrap_servers=['localhost:9092'],
                                          compression_type='gzip',
                                          value_serializer=pickle.dumps,
                                          batch_size=2 ** 16,
                                          )

        # self.buffer = Queue(maxsize=33)

        self._last_marker = 0
        self.counter = 0

        self.remnant = b''
        self.offset = None, None
        # self._last_aux_shape = 0

    # ----------------------------------------------------------------------
    @cached_property
    def scale_factor_eeg(self) -> float:
        """Vector with the correct factors for scale eeg data samples."""
        gain = 24
        # vref = 4.5  # for V
        vref = 4500000  # for uV

        return vref / (gain * ((2 ** 23) - 1))

    # ----------------------------------------------------------------------
    def consume(self) -> None:
        """Infinite loop for read Kafka stream."""
        while True:
            for record in self.consumer_binary:
                logging.debug(f"processing {len(record.value['data'])}")
                self.process(record)

    # ----------------------------------------------------------------------
    def process(self, record: KafkaStream) -> None:
        """Prepare the binary package for a successful unpack and stream.

        Parameters
        ----------
        record
            Kafka stream with binary data.
        """
        buffer = record.value
        context = buffer['context']
        context['timestamp.binary.consume'] = datetime.now().timestamp()

        # Deserialice data
        logging.debug(
            f'Aligning data: renmant({len(self.remnant)}), buffer({len(buffer["data"])})')
        data, self.remnant = self.align_data(self.remnant + buffer['data'])
        logging.debug('aligned')
        if not data.shape[0]:
            logging.debug('No data after alignement')
            self.remnant = b''  # reset deserialicig
            return
        logging.debug(
            f'Deserilizing data: data({data.shape}), context({context})')
        eeg_data, aux = self.deserialize(data, context)
        logging.debug(
            f'deserialized eeg_data({eeg_data.shape}), aux({aux.shape})')

        # Stream
        context['samples'] = eeg_data.shape[1]
        context['timestamp.eeg'] = datetime.now().timestamp()

        logging.debug(f'Streaming')
        self.stream([eeg_data, aux], context)

    # ----------------------------------------------------------------------

    def align_data(self, binary: bytes) -> Tuple[np.ndarray, bytes]:
        """Align data following the headers and footers.

        Parameters
        ----------
        binary
            Data raw from OpenBCI board.

        Returns
        -------
        data_aligned
            Numpy array of shape (`33, LENGTH`) with headers and footer aligned.
        remnant
            This bytes could be used for complete next binary input.
        """
        logging.debug('Binary to np.ndarray')
        data = np.array(list(binary))

        # Search for the the first index with a `BIN_HEADER`
        logging.debug('Looking for BIN_HEADER')
        start = [np.median(np.roll(data, -i, axis=0)[::33])
                 == self.BIN_HEADER for i in range(33)].index(True)

        if (start == 0) and (data.shape[0] % 33 == 0):
            logging.debug('No alignment necesary')
            data_aligned = data
            remnant = b''
        else:
            # Fix the offset to complete 33 bytes divisible array
            logging.debug('Alingnig...')
            end = (data.shape[0] - start) % 33
            logging.debug(
                f'Alingnig data({len(data)}) at data({start}:-{end})')
            data_aligned = data[start:-end]
            logging.debug('Saving remnant')
            remnant = binary[-end:]

        logging.debug('Reshaping')
        data_aligned = data_aligned.reshape(-1, 33)

        return data_aligned, remnant

    # ----------------------------------------------------------------------
    def deserialize(self, data: np.ndarray, context: Dict[str, Any]) -> None:
        """From signed 24-bits integer to signed 32-bits integer.

        Parameters
        ----------
        data
            Numpy array of shape (`33, LENGTH`)
        context
            Information from the acquisition side useful for deserializing and
            that will be packaged back in the stream.
        """

        # EGG
        eeg_data = data[:, 2:26]
        eeg_data = getattr(self, f'deserialize_eeg_{context["connection"]}')(
            eeg_data, data[:, 1], context)

        # Auxiliar
        stop_byte = int((np.median(data[:, -1])))
        aux = self.deserialize_aux(stop_byte, data[:, 26:32], context)
        self.LAST_AUX_SHAPE = aux.shape

        # Stream
        channels = np.array(list(context['montage'].keys())) - 1

        return eeg_data.T[channels], aux.T
        # self.stream([eeg_data.T[channels], aux.T], eeg_data.shape[0], context)

    # ----------------------------------------------------------------------
    def deserialize_eeg_wifi(self, eeg: np.ndarray, ids: np.ndarray, context: Dict[str, Any]) -> np.ndarray:
        """From signed 24-bits integer to signed 32-bits integer by channels.

        The `Cyton data format <https://docs.openbci.com/docs/02Cyton/CytonDataFormat>`_
        says that only can send packages of 33 bits, when a Daisy board is
        attached these same packages will be sent at double speed in favor to
        keep the desired sample rate for 16 channels.

        Parameters
        ----------
        eeg
            Numpy array in signed 24-bits integer (`8, LENGTH`)
        ids
            List of IDs for eeg data.
        context
            Information from the acquisition side useful for deserializing and
            that will be packaged back in the stream.

        Returns
        -------
        eeg_data
            EEG data in microvolts, signed 32-bits integer, (`CHANNELS, LENGTH`),
            if there is a Daisy board `CHANNELS` is 16, otherwise is 8.
        """

        eeg_data = np.array([[rawutil.unpack('>u', bytes(ch))[0]
                              for ch in row.reshape(-1, 3).tolist()] for row in eeg])
        eeg_data = eeg_data * self.scale_factor_eeg

        if context['daisy']:

            # # If offset, the pair index condition must change
            if np.array(self.offset[0]).any():
                eeg_data = np.concatenate(
                    [[self.offset[0]], eeg_data], axis=0)
                ids = np.concatenate([[self.offset[1]], ids], axis=0)
                # pair = not pair

            if ids[0] != ids[1]:
                eeg_data = np.delete(eeg_data, 0, axis=0)
                ids = np.delete(ids, 0, axis=0)

            # if not pair dataset, create an offeset
            if eeg_data.shape[0] % 2:
                self.offset = eeg_data[-1], ids[-1]
                eeg_data = np.delete(eeg_data, -1, axis=0)
                ids = np.delete(ids, -1, axis=0)
            else:
                self.offset = None, None

            return eeg_data.reshape(-1, 16)

        return eeg_data

    # ----------------------------------------------------------------------
    def deserialize_eeg_serial(self, eeg: np.ndarray, ids: np.ndarray, context: Dict[str, Any]) -> np.ndarray:
        """From signed 24-bits integer to signed 32-bits integer by channels.

        The `Cyton data format <https://docs.openbci.com/docs/02Cyton/CytonDataFormat>`_
        says that only can send packages of 33 bits, over serial (RFduino) this
        limit is absolute, when a Daisy board is attached these same amount of
        packages will be sent, in this case, the data must be distributed and
        interpolated in order to complete the sample rate.

        Parameters
        ----------
        eeg
            Numpy array in signed 24-bits integer (`8, LENGTH`)
        ids
            List of IDs for eeg data.
        context
            Information from the acquisition side useful for deserializing and
            that will be packaged back in the stream.

        Returns
        -------
        eeg_data
            EEG data in microvolts, signed 32-bits integer, (`CHANNELS, LENGTH`),
            if there is a Daisy board `CHANNELS` is 16, otherwise is 8.
        """

        eeg_data = np.array([[rawutil.unpack('>u', bytes(ch))[0]
                              for ch in row.reshape(-1, 3).tolist()] for row in eeg])
        eeg_data = eeg_data * self.scale_factor_eeg

        if context['daisy']:

            even = not ids[0] % 2

            # If offset, the even index condition must change
            if np.array(self.offset[0]).any():
                eeg_data = np.concatenate(
                    [[self.offset[0]], eeg_data], axis=0)
                ids = np.concatenate([[self.offset[1]], ids], axis=0)
                even = not even

            # if not even dataset, create an offset
            if eeg_data.shape[0] % 2:
                self.offset = eeg_data[-1], ids[-1]
                eeg_data = np.delete(eeg_data, -1, axis=0)
                ids = np.delete(ids, -1, axis=0)

            # Data can start with a even or odd id
            if even:
                board = eeg_data[::2]
                daisy = eeg_data[1::2]
            else:
                daisy = eeg_data[::2]
                board = eeg_data[1::2]

            board = np.array([np.interp(np.arange(0, p.shape[0], 0.5), np.arange(
                p.shape[0]), p) for p in board.T]).T
            daisy = np.array([np.interp(np.arange(0, p.shape[0], 0.5), np.arange(
                p.shape[0]), p) for p in daisy.T]).T

            eeg = np.concatenate([np.stack(board), np.stack(daisy)], axis=1)

        else:
            eeg = eeg_data

        return eeg

    # ----------------------------------------------------------------------
    @classmethod
    def deserialize_aux(cls, stop_byte: int, aux: int, context: Dict[str, Any]) -> np.ndarray:
        """Determine the content of `AUX` bytes and format it.

        Auxialiar data could contain different kind of information: accelometer,
        user defined, time stamped and digital or analog inputs.
        The context of `AUX` bytes are determined by the stop byte.

        If `stop_byte` is `0xc0` the `AUX` bytes contain `Standard with accel`,
        this data are packaged at different frequency, they will be show up each
        10 or 11 packages, the final list will contain accelometer value in `G`
        units for axis `X`, `Y` and `Z` respectively and `None` when are not
        availables.

        If `stop_byte` is `0xc1` the `AUX` bytes contain `Standard with raw aux`,
        there are 3 types of raw data: `digital` in wich case the final list
        will contain the values for `D11`, `D12`, `D13`, `D17`, `D18`; `analog`
        with the values for `A7` (`D13`), `A6` (`D12`), `A5` (`D11`); `markers`
        data contain the the marker sended with `send_marker()` method.

        Parameters
        ----------
        stop_byte
             0xCX where X is 0-F in hex.
        aux
            6 bytes of data defined and parsed based on the `Footer` bytes.
        context
            Information from the acquisition side useful for deserializing and
            that will be packaged back in the stream.

        Returns
        -------
        list
            Correct data formated.

        """

        # Standard with accel
        if stop_byte == 0xc0:
            return 0.002 * \
                np.array([struct.unpack('>hhh', a.astype('i1').tobytes())
                          for a in aux]) / 16

        # Standard with raw aux
        elif stop_byte == 0xc1:

            if context['boardmode'] == 'analog':
                if context['connection'] == 'wifi':
                    # A7, A6, A5
                    # D13, D12, D11
                    return np.array([[rawutil.unpack('>H', bytes(ch))[0] for ch in row.reshape(-1, 2).tolist()][:2] for row in aux])
                else:
                    # A7, A6, A5
                    # D13, D12, D11
                    return np.array([[rawutil.unpack('>H', bytes(ch))[0] for ch in row.reshape(-1, 2).tolist()] for row in aux])

            elif context['boardmode'] == 'digital':
                if context['connection'] == 'wifi':
                    # D11, D12, D17
                    return aux[:, [0, 1, 3]]
                else:
                    # D11, D12, D13, D17, D18
                    return aux[:, :-1]

            elif context['boardmode'] == 'marker':
                # Some time for some reason, marker not always send back from
                # OpenBCI, so this module implement a strategy to send a burst of
                # markers but read back only one.
                a = aux[:, 1]
                a[a > ord('Z')] = 0
                a[a < ord('A')] = 0
                return a

        # User defined
        elif stop_byte == 0xc2:
            pass

        # Time stamped set with accel
        elif stop_byte == 0xc3:
            pass

        # Time stamped with accel
        elif stop_byte == 0xc4:
            pass

        # Time stamped set with raw auxcalculate_sample_rate
        elif stop_byte == 0xc5:
            pass

        # Time stamped with raw aux
        elif stop_byte == 0xc6:
            pass

        return np.zeros(cls.LAST_AUX_SHAPE)

    # ----------------------------------------------------------------------
    def stream(self, data, context):
        """Kafka produser.

        Stream data to network.

        Parameters
        ----------
        data : list
            The EEG data format.

        """

        data_ = {'context': context.copy(),
                 'data': data.copy(),
                 }

        self.producer_eeg.send(f'eeg{self.board_id}', data_)
        # future = self.producer_eeg.send(f'eeg{self.board_id}', data_)
        # try:
            # future.get()
        # except Exception as e:
            # logging.error(e)

        logging.debug(f"streamed ({data[0].shape}, {data[1].shape}) samples")


if __name__ == '__main__':
    tranformer = BinaryToEEG(0)
    tranformer.consume()
