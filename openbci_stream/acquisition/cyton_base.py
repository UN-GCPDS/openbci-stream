"""
==========
Cyton Base
==========
"""

import re
import time
import logging
import pickle
from datetime import datetime
from functools import cached_property

import numpy as np

from scipy.interpolate import interp1d

# from functools import cached_property
from abc import ABCMeta, abstractmethod
from multiprocessing import Process, Manager
from threading import Thread

from .binary_stream import BinaryStream
# from .consumer import OpenBCIConsumer

from kafka import KafkaConsumer
# from kafka.errors import NoBrokersAvailable
# from openbci_stream import doc_urls
# import traceback

from ..utils import HDF5Writer, interpolate_datetime

########################################################################


class CytonConstants:
    """"""

    VREF = 4.5

    BIN_HEADER = 0xa0

    START_STREAM = b'b'
    STOP_STREAM = b's'

    DEACTIVATE_CHANEL = b'12345678qwertyui'
    ACTIVATE_CHANEL = b'!@#$%^&*QWERTYUI'
    CHANNEL_SETTING = b'12345678QWERTYUI'

    TEST_GND = b'0'      # Connect to internal GND (VDD - VSS)
    TEST_1X_SLOW = b'-'  # Connect to test signal 1xAmplitude, slow pulse
    TEST_1X_FAST = b'='  # Connect to test signal 1xAmplitude, fast pulse
    TEST_DC = b'p'       # Connect to DC signal
    TEST_2X_SLOW = b'['  # Connect to test signal 2xAmplitude, slow pulse
    TEST_2X_FAST = b']'  # Connect to test signal 2xAmplitude, fast pulse

    POWER_DOWN_ON = b'0'
    POWER_DOWN_OFF = b'1'

    GAIN_1 = b'0'
    GAIN_2 = b'1'
    GAIN_4 = b'2'
    GAIN_6 = b'3'
    GAIN_8 = b'4'
    GAIN_12 = b'5'
    GAIN_24 = b'6'

    ADSINPUT_NORMAL = b'0'
    ADSINPUT_SHORTED = b'1'
    ADSINPUT_BIAS_MEAS = b'2'
    ADSINPUT_MVDD = b'3'
    ADSINPUT_TEMP = b'4'
    ADSINPUT_TESTSIG = b'5'
    ADSINPUT_BIAS_DRP = b'6'
    ADSINPUT_BIAS_DRN = b'7'

    BIAS_REMOVE = b'0'
    BIAS_INCLUDE = b'1'

    SRB2_DISCONNECT = b'0'
    SRB2_CONNECT = b'1'

    SRB1_DISCONNECT = b'0'
    SRB1_CONNECT = b'1'

    DEFAULT_CHANNELS_SETTINGS = b'd'
    DEFAULT_CHANNELS_SETTINGS_REPORT = b'D'

    TEST_SIGNAL_NOT_APPLIED = b'0'
    TEST_SIGNAL_APPLIED = b'1'

    SD_DATA_LOGGING_5MIN = b'A'
    SD_DATA_LOGGING_15MIN = b'S'
    SD_DATA_LOGGING_30MIN = b'F'
    SD_DATA_LOGGING_1HR = b'G'
    SD_DATA_LOGGING_2HR = b'H'
    SD_DATA_LOGGING_4HR = b'J'
    SD_DATA_LOGGING_12HR = b'K'
    SD_DATA_LOGGING_24HR = b'L'
    SD_DATA_LOGGING_14S = b'a'
    SD_DATA_LOGGING_STOP = b'j'

    QUERY_REGISTER = b'?'
    SOFT_RESET = b'v'

    USE_8CH_ONLY = b'c'
    USE_16CH_ONLY = b'C'

    TIME_STAMP_ON = b'<'
    TIME_STAMP_OFF = b'>'

    SAMPLE_RATE_16KSPS = b'~0'
    SAMPLE_RATE_8KSPS = b'~1'
    SAMPLE_RATE_4KSPS = b'~2'
    SAMPLE_RATE_2KSPS = b'~3'
    SAMPLE_RATE_1KSPS = b'~4'
    SAMPLE_RATE_500SPS = b'~5'
    SAMPLE_RATE_250SPS = b'~6'
    SAMPLE_RATE_GET = b'~~'

    SAMPLE_RATE_VALUE = {
        b'~0': 16e3,
        b'~1': 8e3,
        b'~2': 4e3,
        b'~3': 2e3,
        b'~4': 1e3,
        b'~5': 500,
        b'~6': 250,
    }

    BOARD_MODE_DEFAULT = b'/0'  # Sends accelerometer data in aux bytes
    BOARD_MODE_DEBUG = b'/1'    # Sends serial output over the external serial
                                # port which is helpful for debugging.
    BOARD_MODE_ANALOG = b'/2'   # Reads from analog pins A5(D11), A6(D12) and
                                # if no wifi shield is present, then A7(D13)
                                # as well.
    BOARD_MODE_DIGITAL = b'/3'  # Reads from analog pins D11, D12 and D17.
                                # If no wifi present then also D13 and D18.
    BOARD_MODE_MARKER = b'/4'   # Turns accel off and injects markers
                                # into the stream by sending `X where X is any
                                # char to add to the first AUX byte.
    BOARD_MODE_GET = b'//'      # Get current board mode

    BOARD_MODE_VALUE = {
        b'/0': 'default',
        b'/1': 'debug',
        b'/2': 'analog',
        b'/3': 'digital',
        b'/4': 'marker',
    }

    WIFI_SHIELD_ATTACH = b'{'
    WIFI_SHIELD_DEATTACH = b'}'
    WIFI_SHIELD_STATUS = b':'
    WIFI_SHIELD_RESET = b';'

    VERSION = b'V'


########################################################################
class CytonBase(CytonConstants, metaclass=ABCMeta):
    """
    The Cyton data format and SDK define all interactions and capabilities of
    the board, the full instructions can be found in the official package.

      * https://docs.openbci.com/Hardware/03-Cyton_Data_Format
      * https://docs.openbci.com/OpenBCI%20Software/04-OpenBCI_Cyton_SDK
    """

    # Flags
    READING = None

    # ----------------------------------------------------------------------
    def __init__(self, daisy, capture_stream, montage, streaming_package_size):
        """"""
        # try:
            # self.binary_stream = BinaryStream()
        # except NoBrokersAvailable:
            # traceback.print_exc()
            # logging.error('#' + '-' * 70)
            # logging.error('Kafka broker is not available!')
            # logging.error(f'Check {doc_urls.CONFIGURE_KAFKA} for instructions.')

        self.sample_rate = 250

        # Daisy before Montage
        if daisy in [True, False]:
            self.daisy = daisy
        elif daisy == 'auto':
            self.daisy = self.daisy_attached()

        # Montage
        self.montage = montage

        # Data Structure
        self._data_eeg = Manager().Queue()
        self._data_aux = Manager().Queue()
        self._data_markers = Manager().Queue()
        self._data_timestamp = Manager().Queue()
        # self._data_offset = Manager().Queue()

        # self.sample_rate = sample_rate
        self.reset_input_buffer()

        # Autocapture stream
        self._auto_capture_stream = capture_stream

        self.streaming_package_size = streaming_package_size

        # self.default_init()

    # ----------------------------------------------------------------------

    @property
    def gain(self):
        """Vector with the gains for each channel."""

        # TODO
        # A method for change the ganancy of each channel must be writed here

        if hasattr(self, '_gain'):
            return self._gain
        else:
            return [24, 24, 24, 24, 24, 24, 24, 24]

    # ----------------------------------------------------------------------
    @property
    def scale_factor_eeg(self):
        """Vector with the correct factors for scale eeg data samples."""

        return [self.VREF / (gain * ((2 ** 23) - 1)) for gain in self.gain]

    # ----------------------------------------------------------------------
    @property
    def boardmode(self):
        """"""
        # if hasattr(self, '_boardmode') and self._boardmode:
            # return self._boardmode

        self.command(self.STOP_STREAM)
        response = self.command(self.BOARD_MODE_GET)

        for mode in [b'analog', b'digital', b'debug', b'default', b'marker']:
            if mode in response:
                return mode.decode()

        logging.warning(
            'Stream must be stoped for read the current boardmode')

    # # ----------------------------------------------------------------------
    # @boardmode.setter
    # def boardmode(self, mode):
        # """"""
        # self.command(mode)
        # self._boardmode = self.BOARD_MODE_VALUE[mode]

    # # ----------------------------------------------------------------------
    # @property
    # def sample_rate(self):
        # """"""
        # response = self.command(self.SAMPLE_RATE_GET)
        # # if response is None:
            # # return self.sample_rate
        # try:
            # value, multiple, _ = re.findall(
                # '([0-9]+)([K]*)(Hz)', response.decode())[0]
            # # return f'SAMPLE_RATE_{value}{multiple}SPS'
            # return self.SAMPLE_RATE_VALUE[getattr(self, f'SAMPLE_RATE_{value}{multiple}SPS')]
        # except:
            # return self.sample_rate

    # # ----------------------------------------------------------------------
    # @sample_rate.setter
    # def sample_rate(self, sr):
        # """"""
        # if not sr in self.SAMPLE_RATE_VALUE.keys():
            # sr = getattr(self, sr)
        # self.command(sr)

    # ----------------------------------------------------------------------
    @property
    def montage(self):
        """"""
        return self._montage

    # ----------------------------------------------------------------------
    @montage.setter
    def montage(self, montage):
        """Define the information with que electrodes names.

        If a list is passed the format will be supposed with index as channels,
        the index can be set explicitly with a dictionary instead of a list.

        Parameters
        ----------
        montage : list, dict, None, optional
            Decription of channels used.
        """

        if isinstance(montage, (bytes)):
            montage = pickle.loads(montage)

        if isinstance(montage, (list, tuple, range)):
            self._montage = {i: ch for i, ch in enumerate(montage)}
        elif isinstance(montage, (dict)):
            self._montage = {i: ch for i, ch in enumerate(montage.values())}
        else:

            if self.daisy:
                self._montage = {i: f'ch{i+1}' for i in range(16)}
            elif not self.daisy:
                self._montage = {i: f'ch{i+1}' for i in range(8)}

    # ----------------------------------------------------------------------
    @property
    def streaming(self):
        """"""
        # TODO
        if hasattr(self, 'binary_stream'):
            self.binary_stream.producer

    # ----------------------------------------------------------------------

    def deactivate_channel(self, channels):
        """Deactivate the channels specified."""

        chain = ''.join([chr(self.DEACTIVATE_CHANEL[ch - 1])
                         for ch in channels]).encode()
        self.command(chain)
        # [self.command(self.DEACTIVATE_CHANEL[ch]) for ch in channels]

    # ----------------------------------------------------------------------
    def activate_channel(self, channels):
        """Activate the channels specified."""

        chain = ''.join([chr(self.ACTIVATE_CHANEL[ch - 1])
                         for ch in channels]).encode()
        self.command(chain)
        # [self.command(self.ACTIVATE_CHANEL[ch]) for ch in channels]

    # ----------------------------------------------------------------------
    def command(self, c):
        """Send a command to device.

        Before send the commmand the input buffer is cleared, and after that
        waits 300 ms for a response.

        Parameters
        ----------
        c : bytes
            Command to send.

        Returns
        -------
        str
            If the command generate a response this will be sended back.
        """

        if hasattr(self, c.decode()):
            c = getattr(self, c.decode())

        if c in list(self.SAMPLE_RATE_VALUE.keys()):
            self.sample_rate = int(self.SAMPLE_RATE_VALUE[c])

        self.reset_input_buffer()
        self.write(c)
        time.sleep(0.3)
        response = self.read(2**11)
        logging.info(f'Writed: {c}')
        if len(response) > 100:
            logging.info(f'Responded: {response[:100]}...')
        else:
            logging.info(f'Responded: {response}')

        if hasattr(response, 'encode'):
            response = response.encode()
        elif isinstance(response, (list)):
            response = ''.join([chr(r) for r in response]).encode()

        return response

    # ----------------------------------------------------------------------
    def channel_settings(self, channels,
                         power_down=CytonConstants.POWER_DOWN_ON,
                         gain=CytonConstants.GAIN_24,
                         input_type=CytonConstants.ADSINPUT_NORMAL,
                         bias=CytonConstants.BIAS_INCLUDE,
                         srb2=CytonConstants.SRB2_CONNECT,
                         srb1=CytonConstants.SRB1_DISCONNECT):
        """Channel Settings commands.

        Parameters
        ----------
        channels : list
            List of channels that will share the configuration specified.
        power_down : bytes, optional
            POWER_DOWN_ON (default), POWER_DOWN_OFF.
        gain: bytes, optional
            GAIN_24 (default), GAIN_12, GAIN_8, GAIN_6, GAIN_4, GAIN_2, GAIN_1.
        input_type : bytes, optional
            Select the ADC channel input source: ADSINPUT_NORMAL (default),
            ADSINPUT_SHORTED, ADSINPUT_BIAS_MEAS, ADSINPUT_MVDD, ADSINPUT_TEMP,
            ADSINPUT_TESTSIG, ADSINPUT_BIAS_DRP, ADSINPUT_BIAS_DRN,
        bias : bytes, optional
            Select to include the channel input in BIAS generation:
            BIAS_INCLUDE (default), BIAS_REMOVE.
        srb2 : bytes, optional
            Select to connect this channel’s P input to the SRB2 pin. This
            closes a switch between P input and SRB2 for the given channel,
            and allows the P input also remain connected to the ADC:
            SRB2_CONNECT (default), SRB2_DISCONNECT.
        srb1 : bytes, optional
            Select to connect all channels’ N inputs to SRB1. This effects all
            pins, and disconnects all N inputs from the ADC:
            SRB1_DISCONNECT (default), SRB1_CONNECT.

        Returns
        -------

        On success:

          * If streaming, no confirmation of success. Note: WiFi Shields will always get a response, even if streaming.
          * If not streaming, returns Success: Channel set for 3$$$, where 3 is the channel that was requested to be set.

        On failure:

          * If not streaming, NOTE: WiFi shield always sends the following responses without $$$
              * Not enough characters received, Failure: too few chars$$$ (example user sends x102000X)
              * 9th character is not the upper case `X`, Failure: 9th char not X$$$ (example user sends x1020000V)
              * Too many characters or some other issue, Failure: Err: too many chars$$$
          * If not all commands are not received within 1 second, Timeout processing multi byte message - please send all commands at once as of v2$$$

        """

        start = b'x'
        end = b'X'

        self.reset_input_buffer()

        chain = b''
        for ch in channels:
            ch = chr(self.CHANNEL_SETTING[ch - 1]).encode()
            chain += b''.join([start, ch, power_down, gain, input_type, bias,
                               srb2, srb1, end])

        self.command(chain)
            # time.sleep(0.3)
            # response = self.read(2**11)

            # logging.info(f'Writed: {chain}')
            # if len(response) > 100:
                # logging.info(f'Responded: {response[:100]}...')
            # else:
                # logging.info(f'Responded: {response}')

        # time.sleep(0.3)
        # return self.read(2**11)

    # ----------------------------------------------------------------------
    def leadoff_impedance(self, channels, pchan=CytonConstants.TEST_SIGNAL_NOT_APPLIED,
                          nchan=CytonConstants.TEST_SIGNAL_APPLIED):
        """LeadOff Impedance Commands

        Parameters
        ----------
        channels : list
            List of channels that will share the configuration specified.
        pchan : bytes, optional
            TEST_SIGNAL_NOT_APPLIED (default), TEST_SIGNAL_APPLIED.
        nchan : bytes, optional
            TEST_SIGNAL_APPLIED (default), TEST_SIGNAL_NOT_APPLIED.

        Returns
        -------

        On success:

          * If streaming, no confirmation of success. Note: WiFi Shields will always get a response, even if streaming.
          * If not streaming, returns Success: Lead off set for 4$$$, where 4 is the channel that was requested to be set.

        On failure:

          * If not streaming, NOTE: WiFi shield always sends the following responses without $$$
              * Not enough characters received, Failure: too few chars$$$ (example user sends z102000Z)
              * 5th character is not the upper case ‘Z’, Failure: 5th char not Z$$$ (example user sends z1020000X)
              * Too many characters or some other issue, Failure: Err: too many chars$$$
          * If not all commands are not received within 1 second, Timeout processing multi byte message - please send all commands at once as of v2$$$

        """

        start = b'z'
        end = b'Z'

        self.reset_input_buffer()
        chain = b''
        for ch in channels:
            ch = chr(self.CHANNEL_SETTING[ch - 1]).encode()
            chain += b''.join([start, ch, pchan, nchan, end])
        self.command(chain)
            # time.sleep(0.3)
            # response = self.read(2**11)

            # logging.info(f'Writed: {chain}')
            # if len(response) > 100:
                # logging.info(f'Responded: {response[:100]}...')
            # else:
                # logging.info(f'Responded: {response}')

        # time.sleep(0.3)
        # return self.read(2**11)

    # ----------------------------------------------------------------------
    def send_marker(self, marker, burst=4):
        """Send marker to device.

        The marker sended will be added to the `AUX` bytes in the next data
        input.

        The OpenBCI markers does not work as well as expected, so this module
        implement an strategy for make it works. A burst markers are sended but
        just one are readed, this add a limitation: No more that one marker each
        300 ms are permitted.

        Parameters
        ----------
        marker : str, bytes, int
            A single value required.
        burst : int, optional
            How many times the marker will be send.

        """

        if isinstance(marker, int):
            marker = chr(marker)
        elif isinstance(marker, bytes):
            marker = marker.decode()

        if ord('A') <= ord(marker) <= ord('Z'):
            self.write(f'`{marker}'.encode() * burst)
        else:
            logging.warning(
                f'Marker must be between {ord("A")} and {ord("Z")}')

    # ----------------------------------------------------------------------
    def daisy_attached(self):
        """Check if a Daisy module is attached.

        This command will activate the Daisy module is this is available.

        Returns
        -------
        bool
            Daisy module activated.

        """
        # self.command(self.SOFT_RESET)  # to update the status information
        response = self.command(self.USE_16CH_ONLY)
        # self.activate_channel(range(16))

        if not response:
            # logging.warning(f"Channels no setted correctly")
            return self.daisy_attached()

        daisy = not (('no daisy to attach' in response.decode(errors='ignore')) or
                     ('8' in response.decode(errors='ignore')))

        # # if self.montage:
            # # channels = self.montage.keys()
        # if not self._montage and daisy:
            # # channels = range(16)
            # self.montage = range(16)
        # elif not self._montage and not daisy:
            # # channels = range(8)
            # self.montage = range(8)

        # # self.default_init()

        # logging.info(f"Using channels: {channels}")

        return daisy

    # # ----------------------------------------------------------------------
    # def default_init(self, pchan=TEST_SIGNAL_NOT_APPLIED, nchan=TEST_SIGNAL_APPLIED):
        # """"""
        # channels = self.montage.keys()
        # self.leadoff_impedance(channels,
                               # pchan,
                               # nchan,
                               # )
        # # self.leadoff_impedance(channels,
                               # # self.TEST_SIGNAL_NOT_APPLIED,  # pchan
                               # # self.TEST_SIGNAL_APPLIED,  # nchan
                               # # )
        # # self.leadoff_impedance(channels,
                               # # self.TEST_SIGNAL_NOT_APPLIED,  # pchan
                               # # self.TEST_SIGNAL_NOT_APPLIED,  # nchan
                               # # )
        # self.activate_channel(channels)

    # ----------------------------------------------------------------------
    def capture_stream(self):
        """"""
        # For prevent circular import
        from .consumer import OpenBCIConsumer

        self.reset_buffers()

        def bulk_buffer():
            """"""
            with OpenBCIConsumer() as stream:
                for message in stream:
                    if message.topic == 'eeg':

                        eeg, aux = message.value['data']

                        self._data_eeg.put(eeg)
                        self._data_aux.put(aux)

                        timestamp = np.zeros(message.value['samples'])
                        timestamp[-1] = message.value['binary_created']
                        self._data_timestamp.put(timestamp)

                    elif message.topic == 'marker':

                        timestamp = message.value['timestamp']
                        # timestamp = message.timestamp / 1000
                        marker = message.value['marker']
                        self._data_markers.put((timestamp, marker))

                    # self._data_offset.put(message.offset)

        self.persistent_process = Process(target=bulk_buffer)
        self.persistent_process.start()

    # ----------------------------------------------------------------------
    def _wait_for_data(self):
        """"""
        t0 = time.time()
        if hasattr(self, 'persistent_process'):
            while not self.eeg_buffer.qsize() and (time.time() - t0 < 10):
                time.sleep(0.25)
        else:
            logging.warning(
                f"`wait_for_data` only works with `capture_stream=True`")

    # ----------------------------------------------------------------------
    def _wait_for_no_data(self):
        """"""
        t0 = time.time()
        if hasattr(self, 'persistent_process'):

            a = self.eeg_buffer.qsize()
            time.sleep(3)
            b = self.eeg_buffer.qsize()

            while a != b:

                a = self.eeg_buffer.qsize()
                time.sleep(3)
                b = self.eeg_buffer.qsize()

        else:
            logging.warning(
                f"`wait_for_no_data` only works with `capture_stream=True`")

    # # ----------------------------------------------------------------------
    # def stack(self, offset=0):
        # """"""
        # if not self.eeg_buffer.qsize():
            # return np.array([[], [], []])

        # # move offset
        # [self.eeg_buffer.get() for _ in range(offset)]
        # [self.eeg_timestamp.get() for _ in range(offset)]
        # # [self.eeg_timestamp.get() for _ in range(offset)]

        # qq = [self.eeg_buffer.get() for _ in range(self.eeg_buffer.qsize())]
        # eeg = np.concatenate(np.array(qq).T[0], axis=1)

        # try:
            # aux = np.concatenate(np.array(qq).T[1], axis=1)
        # except np.AxisError:  # For markers
            # aux = np.concatenate(np.array(qq).T[1])

        # ww = [self.eeg_timestamp.get()
              # for _ in range(self.eeg_timestamp.qsize())]
        # timestamp = np.concatenate(ww)

        # nonzero = np.nonzero(timestamp)
        # args = np.arange(len(timestamp))
        # interp = interp1d(
            # args[nonzero], timestamp[nonzero], fill_value="extrapolate")
        # timestamp = interp(args)

        # ww = [self.eeg_markers.get()
              # for _ in range(self.eeg_markers.qsize())]
        # markers = list(zip(*ww))

        # return np.array([eeg, aux, timestamp, markers])

    # ----------------------------------------------------------------------
    def start_stream(self, clear):
        """"""

        # try:
        self.binary_stream = BinaryStream(self.streaming_package_size)
        # except NoBrokersAvailable:
            # traceback.print_exc()
            # logging.error('#' + '-' * 70)
            # logging.error('Kafka broker is not available!')
            # logging.error(f'Check {doc_urls.CONFIGURE_KAFKA} for instructions.')

        if clear:
            self.reset_buffers()
            self.reset_input_buffer()

        if self._auto_capture_stream:
            self.capture_stream()

    # ----------------------------------------------------------------------
    def stop_stream(self):
        """"""
        if hasattr(self, 'persistent_process'):
            self.persistent_process.terminate()
            self.persistent_process.join()

    # ----------------------------------------------------------------------
    @abstractmethod
    def close(self):
        """Device handled process, stop data stream."""
        pass

    # ----------------------------------------------------------------------
    @abstractmethod
    def write(self):
        """"""
        """Device handled process, write bytes."""
        pass

    # ----------------------------------------------------------------------
    @abstractmethod
    def read(self):
        """Device handled process, read binary data."""
        pass

    # ----------------------------------------------------------------------
    def reset_input_buffer(self):
        """Device handled process, flush input data."""
        pass

    ############################################################################
    # Preprocessing queue properties

    # ----------------------------------------------------------------------
    @property
    def eeg_buffer(self):
        """Return the deserialized data buffer."""

        return self._data_eeg

    # ----------------------------------------------------------------------
    @property
    def timestamp_buffer(self):
        """Return the deserialized data buffer."""

        return self._data_timestamp

    # ----------------------------------------------------------------------
    @property
    def markers_buffer(self):
        """Return the deserialized data buffer."""

        return self._data_markers

    # ----------------------------------------------------------------------
    @property
    def aux_buffer(self):
        """Return the deserialized data buffer."""

        return self._data_aux

    ############################################################################
    # Buffers time series

    # ----------------------------------------------------------------------
    # @property
    @cached_property
    def eeg_time_series(self):
        """"""
        eeg = [self._data_eeg.get() for _ in range(self._data_eeg.qsize())]

        if eeg:
            eeg = np.concatenate(eeg, axis=1)
            return eeg
        else:
            logging.warning(
                f'No EEG data captured, make sure to activate `capture_stream` in the {self} instantiation\n'
                f'This too could be because the `stream_eeg` daemon was not running.')
            return np.array([])

    # ----------------------------------------------------------------------
    # @property
    @cached_property
    def aux_time_series(self):
        """"""
        aux = [self._data_aux.get() for _ in range(self._data_aux.qsize())]

        try:
            aux = np.concatenate(aux, axis=1)
        except np.AxisError:
            aux = np.concatenate(aux, axis=0)

        return aux

    # ----------------------------------------------------------------------
    @cached_property
    def timestamp_time_series(self):
        """"""
        timestamp = [self._data_timestamp.get() for _ in range(self._data_timestamp.qsize())]
        timestamp = np.concatenate(timestamp, axis=0)
        length = self.eeg_time_series.shape[1]
        sample_rate = self.sample_rate

        timestamp = interpolate_datetime(timestamp, length, sample_rate)

        return timestamp

    # ----------------------------------------------------------------------
    @cached_property
    def markers(self):
        """"""
        markers = {}
        for t, marker in [self._data_markers.get() for _ in range(self._data_markers.qsize())]:
            markers.setdefault(marker, []).append(t)

        return markers

    # ----------------------------------------------------------------------
    def reset_buffers(self):
        """Discard buffers."""

        for buffer in [self._data_eeg,
                       self._data_aux,
                       self._data_markers,
                       self._data_timestamp,
                       ]:

            try:
                with buffer.mutex:
                    buffer.clear()
            except:
                while not buffer.empty():
                    buffer.get()

        for cached in ['eeg_time_series',
                       'aux_time_series',
                       'markers_time_series',
                       'timestamp_time_series',
                       ]:
            if cached in self.__dict__:
                del self.__dict__[cached]

    # ----------------------------------------------------------------------
    def stream(self, s=1, clear=True):
        """Start a synchronous process for start stream data.

        This call will hang until time completed.

        Parameters
        ----------
        s : int, optional
            Seconds for data collection.
        clear : bool, optional
            Reset buffer before start data collect.
        raw : bool, optional
            Ignore the deserialize process, all data is stored in binary format.
        """

        self.start_stream(clear)
        time.sleep(s)
        self.stop_stream()

    # # ----------------------------------------------------------------------
    # def get_sample_rate(self):
        # """"""
        # response = self.command(self.SAMPLE_RATE_GET)
        # try:
            # sample_rate = re.findall('[0-9]+', response.decode())[0]
            # return int(sample_rate)
        # except:
            # return None

    # ----------------------------------------------------------------------
    def listen_stream_markers(self, host='localhost', topics=['markers']):
        """"""
        bootstrap_servers = [f'{host}:9092']

        markers_consumer = KafkaConsumer(
            bootstrap_servers=bootstrap_servers,
            # value_deserializer=lambda x: pickle.loads(x),
            # group_id='openbci',
            auto_offset_reset='latest',

        )
        markers_consumer.subscribe(topics)

        def _send_marker():
            for message in markers_consumer:
                marker = message.value
                try:
                    self.send_marker(marker)
                    print(f"MARKER {marker}")
                except Exception as e:
                    print(f"MARKER {e}")
                    pass

        self.stream_markers = Thread(target=_send_marker)
        self.stream_markers.start()

    # ----------------------------------------------------------------------
    def save(self, filename, montage, sample_rate=None):
        """"""
        if sample_rate is None:
            sample_rate = self.sample_rate

        header = {'sample_rate': sample_rate,
                  'datetime': datetime.now().timestamp(),
                  'montage': montage,
                  'channels': self.montage,
                  }

        with HDF5Writer(filename) as writer:
            writer.add_header(header)

            eeg = self.eeg_time_series
            time = self.timestamp_time_series
            aux = self.aux_time_series

            writer.add_eeg(eeg, time)
            writer.add_aux(aux)
            writer.add_markers(self.markers)

            logging.info(f'Writed a vector of shape ({eeg.shape}) for EEG data')
            logging.info(f'Writed a vector of shape ({time.shape}) for time data')
            logging.info(f'Writed a vector of shape ({aux.shape}) for aux data')
            if self.markers:
                logging.info(f'Writed {self.markers.keys()} markers')
