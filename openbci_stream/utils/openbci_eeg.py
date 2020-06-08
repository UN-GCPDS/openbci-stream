"""
=============
Binary to EEG
=============

A transformer for Kafka that read binary data and stream EEG data.

Binary -> Kafka-Transformer -> EEG



"""

import pickle
import struct
import numpy as np
from queue import Queue
from threading import Thread
from datetime import datetime

from kafka import KafkaConsumer, KafkaProducer

from openbci_stream.utils import autokill_process
autokill_process(name='binary_2_eeg')


########################################################################
class BinaryToEEG:
    """"""
    VREF = 4.5
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

    # ----------------------------------------------------------------------
    @property
    def gain(self):
        """Vector with the gains for each channel."""

        # TODO
        # A method for change the ganancy of each channel must be writed here
        return [24, 24, 24, 24, 24, 24, 24, 24]

    # ----------------------------------------------------------------------
    @property
    def scale_factor_eeg(self):
        """Vector with the correct factors for scale eeg data samples."""

        return [self.VREF / (gain * ((2 ** 23) - 1)) for gain in self.gain]

    # ----------------------------------------------------------------------
    def consume(self):
        """Infinite loop for read Kafka stream."""
        while True:
            for record in self.consumer_binary:
                self.process(record)

    # ----------------------------------------------------------------------
    def process(self, record):
        """Prepare the binary package for a successful unpack and stream.

        Parameters
        ----------
        record : int
            Kafka stream with bibary data.
        """

        buffer = record.value
        context = buffer['context']
        self.created = context['created']

        data, self.remnant = self.align_data(self.remnant + buffer['data'])

        # Thread for unpack data
        self.b = Thread(target=self.deserialize, args=(data, context))
        self.b.start()
        # self.deserialize(data)

    # ----------------------------------------------------------------------

    def align_data(self, data):
        """"""
        n = len(data) % 33
        if n:
            data, ex = data[:-n], data[-n:]
        else:
            ex = b''

        data = np.array(list(data)).reshape(-1, 33)

        data_align = data.reshape(-1)
        indexes = np.argwhere(data_align == self.BIN_HEADER).reshape(1, -1)[0]
        data_align = np.array([data_align[i:i + 33] for i in indexes][:-1])

        non_33 = np.argwhere(
            [len(a) != 33 for a in data_align]).reshape(1, -1)[0]
        data_align = np.delete(data_align, non_33, axis=0)
        data_align = np.stack(data_align)

        no_data = np.argwhere(
            np.array([hex(int(b))[2] for b in data_align[:, -1]]) != 'c').reshape(1, -1)[0]
        data_full = np.delete(data_align, no_data, axis=0)

        if data_full.shape[0] % 2:
            remnant = data_full[-1]
            data_full = data_full[:-1]
        else:
            remnant = np.array([])

        # , bytes(ex2.tolist()) + bytes(remnant.tolist())  + ex
        return data_full, b''

    # ----------------------------------------------------------------------

    def deserialize(self, data, context):
        """Fom binary to EEG.

        Parameters
        ----------
        data : list
            Kafka stream with bibary data.
        """
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
        # print(f'deserialize_eeg_{context["connection"]}', f'Daisy: {context["daisy"]}', context['boardmode'], eeg_data.shape, aux.shape)
        self.stream([eeg_data.T, aux.T], eeg_data.shape[0], context)

    # ----------------------------------------------------------------------
    def deserialize_eeg_wifi(self, eeg, *_):
        """WiFi bibary not compress data.
        """
        eeg = np.insert(eeg, range(3, eeg.shape[1] + 1, 3), 0, axis=1)
        eeg_data = np.array(memoryview(eeg.astype('i1').tostring()).cast(
            'I')).reshape(-1, 8) * self.scale_factor_eeg

        board = eeg_data[::2]
        daisy = eeg_data[1::2]
        eeg = np.concatenate([board, daisy], axis=1)

        return eeg

    # ----------------------------------------------------------------------
    def deserialize_eeg_serial(self, eeg, pair, context):
        """Uncompress serial data.
        """
        eeg = np.insert(eeg, range(3, eeg.shape[1] + 1, 3), 0, axis=1)
        eeg_data = np.array(memoryview(eeg.astype('i1').tostring()).cast(
            'I')).reshape(-1, 8) * self.scale_factor_eeg

        if context['daisy']:
            # print('daisy')

            if pair:
                board = eeg_data[::2]
                daisy = eeg_data[1::2]
            else:
                daisy = eeg_data[::2]
                board = eeg_data[1::2]

            board = np.array([np.interp(np.arange(0, p.shape[0], 0.5),
                                        np.arange(p.shape[0]), p) for p in board.T]).T
            daisy = np.array([np.interp(np.arange(0, p.shape[0], 0.5),
                                        np.arange(p.shape[0]), p) for p in daisy.T]).T

            daisy = np.roll(daisy, 1, axis=0)
            self.offset, daisy[0] = daisy[0].copy(), self.offset

            eeg = np.concatenate([np.stack(board), np.stack(daisy)], axis=1)

            # print(eeg.shape)

        else:
            # print('NO daisy')
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
            # print('accel')
            return 0.002 * \
                np.array([struct.unpack('>hhh', a.astype('i1').tostring())
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


if __name__ == '__main__':
    tranformer = BinaryToEEG()
    tranformer.consume()


