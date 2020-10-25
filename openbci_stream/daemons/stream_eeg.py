"""
=============
Binary to EEG
=============

A transformer for Kafka that read binary data and stream EEG data.

Binary -> Kafka-Transformer -> EEG

"""

import sys
import pickle
import struct
import numpy as np
from queue import Queue
from threading import Thread
from datetime import datetime
import rawutil

from kafka import KafkaConsumer, KafkaProducer

from openbci_stream.utils import autokill_process
autokill_process(name='binary_2_eeg')

DEBUG = ('--debug' in sys.argv)


########################################################################
class BinaryToEEG:
    """"""
    BIN_HEADER = 0xa0

    # ----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""

        self.consumer_binary = KafkaConsumer(bootstrap_servers=['localhost:9092'],
                                             value_deserializer=pickle.loads,
                                             # group_id='openbci',
                                             auto_offset_reset='latest',
                                             # # heartbeat_interval_ms=500,
                                             )
        self.consumer_binary.subscribe(['binary'])

        self.producer_eeg = KafkaProducer(bootstrap_servers=['localhost:9092'],
                                          compression_type='gzip',
                                          value_serializer=pickle.dumps,
                                          )

        self.buffer = Queue(maxsize=33)
        self._unsampled = Queue(maxsize=3)
        [self._unsampled.put([0] * 8) for i in range(3)]

        self._last_marker = 0
        self.counter = 0

        self.remnant = b''
        self.offset = [0] * 8
        self._last_aux_shape = 0

    # # ----------------------------------------------------------------------
    # @property
    # def gain(self):
        # """Vector with the gains for each channel."""

        # # TODO
        # # A method for change the ganancy of each channel must be writed here
        # return 24

    # ----------------------------------------------------------------------
    @property
    def scale_factor_eeg(self):
        """Vector with the correct factors for scale eeg data samples."""
        gain = 24
        # vref = 4.5  # for V
        vref = 4500000  # for uV

        return vref / (gain * ((2 ** 23) - 1))

    # ----------------------------------------------------------------------
    def consume(self):
        """Infinite loop for read Kafka stream."""
        while True:
            for record in self.consumer_binary:
                if DEBUG:
                    print(f"processing {len(record.value['data'])}")
                self.process(record)

    # ----------------------------------------------------------------------
    def process(self, record):
        """Prepare the binary package for a successful unpack and stream.

        Parameters
        ----------
        record : int
            Kafka stream with binary data.
        """

        buffer = record.value
        context = buffer['context']
        self.created = context['created']

        data, self.remnant = self.align_data(self.remnant + buffer['data'])

        if not data.shape[0]:
            return

        # Thread for unpack data
        self.b = Thread(target=self.deserialize, args=(data, context))
        self.b.start()
        # self.deserialize(data, context)

    # ----------------------------------------------------------------------
    def align_data(self, binary):
        """"""
        data = np.array(list(binary))

        # Search for the the first index with a `BIN_HEADER`
        start = [np.median(np.roll(data, -i, axis=0)[::33]) ==
                 self.BIN_HEADER for i in range(33)].index(True)

        if (start == 0) and (data.shape[0] % 33 == 0):
            data_align = data
            remnant = b''
        else:
            # Fix the offset to complete 33 bytes divisible array
            end = (data.shape[0] - start) % 33
            data_align = data[start:-end]
            remnant = binary[-end:]

        data_align = data_align.reshape(-1, 33)

        # The offset could be used for the next binary data

        return data_align, remnant

    # ----------------------------------------------------------------------
    def deserialize(self, data, context):
        """Fom binary to EEG.

        Parameters
        ----------
        data : list
            Kafka stream with bibary data.
        """

        # From in index
        pair = not data[:, 1][0] % 2

        # EGG
        eeg_data = data[:, 2:26]
        eeg_data = getattr(self, f'deserialize_eeg_{context["connection"]}')(
            eeg_data, pair, context)

        # Auxiliar
        # stop_byte = data[0][-1]
        stop_byte = int((np.median(data[:, -1])))

        aux = self.deserialize_aux(stop_byte, data[:, 26:32], context)
        self._last_aux_shape = aux.shape

        # Stream
        channels = list(context['montage'].keys())
        self.stream([eeg_data.T[channels], aux.T], eeg_data.shape[0], context)

    # ----------------------------------------------------------------------
    def deserialize_eeg_wifi(self, eeg, pair, context):
        """WiFi bibary not compress data.
        """
        eeg_data = np.array([[rawutil.unpack('>u', bytes(ch))[0]
                              for ch in row.reshape(-1, 3).tolist()] for row in eeg])
        eeg_data = eeg_data * self.scale_factor_eeg

        if context['daisy']:

            # If offset, the pair index condition must change
            if np.array(self.offset).any():
                eeg_data = np.concatenate([[self.offset], eeg_data], axis=0)
                pair = not pair

            # if not pair dataset, create an offeset
            if eeg_data.shape[0] % 2:
                self.offset = eeg_data[-1]
                eeg_data = np.delete(eeg_data, -1, axis=0)

            if pair:
                board = eeg_data[::2]
                daisy = eeg_data[1::2]
            else:
                daisy = eeg_data[::2]
                board = eeg_data[1::2]

            return np.concatenate([board, daisy], axis=1)
        else:
            return eeg_data

    # ----------------------------------------------------------------------
    def deserialize_eeg_serial(self, eeg, pair, context):
        """Uncompress serial data.
        """
        eeg_data = np.array([[rawutil.unpack('>u', bytes(ch))[0]
                              for ch in row.reshape(-1, 3).tolist()] for row in eeg])
        eeg_data = eeg_data * self.scale_factor_eeg

        if context['daisy']:

            # If offset, the pair index condition must change
            if np.array(self.offset).any():
                eeg_data = np.concatenate([[self.offset], eeg_data], axis=0)
                pair = not pair

            # if not pair dataset, create an offeset
            if eeg_data.shape[0] % 2:
                self.offset = eeg_data[-1]
                eeg_data = np.delete(eeg_data, -1, axis=0)

            if pair:
                board = eeg_data[::2]
                daisy = eeg_data[1::2]
            else:
                daisy = eeg_data[::2]
                board = eeg_data[1::2]

            board = np.array([np.interp(np.arange(0, p.shape[0], 0.5), np.arange(p.shape[0]), p) for p in board.T]).T
            daisy = np.array([np.interp(np.arange(0, p.shape[0], 0.5), np.arange(p.shape[0]), p) for p in daisy.T]).T

            # # move the last value to the first position
            # daisy = np.roll(daisy, 1, axis=0)
            # # the last position is my offset, and complete with the previous offset
            # self.offset, daisy[0] = daisy[0].copy(), self.offset

            eeg = np.concatenate([np.stack(board), np.stack(daisy)], axis=1)

        else:
            eeg = eeg_data

        if len(context['montage'].keys()) > eeg.shape[1]:
            return eeg
        else:
            return eeg[:, list(context['montage'].keys())]

    # ----------------------------------------------------------------------
    def deserialize_aux(self, stop_byte, aux, context):
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
        stop_byte : int
             0xCX where X is 0-F in hex.

        aux : int
            6 bytes of data defined and parsed based on the `Footer` bytes.


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
                # A7, A6, A5
                # D13, D12, D11
                return aux[:, 1::2]

            elif context['boardmode'] == 'digital':
                # D11, D12, D13, D17, D18
                return np.delete(aux, 4, axis=1)

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

        return np.zeros(self._last_aux_shape)

    # ----------------------------------------------------------------------
    def stream(self, data, samples, context):
        """Kafka produser.

        Stream data to network.

        Parameters
        ----------
        data : list
            The EEG data format.
        samples : int
            The number of samples in this package.

        """
        data_ = {'context': context,
                 'data': data,
                 'binary_created': self.created,
                 'created': datetime.now().timestamp(),
                 'samples': samples,
                 }

        self.producer_eeg.send('eeg', data_)

        if DEBUG:
            print(f"streamed {samples} samples")


if __name__ == '__main__':
    tranformer = BinaryToEEG()
    tranformer.consume()


