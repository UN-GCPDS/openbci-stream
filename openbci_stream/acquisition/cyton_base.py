"""
==========
Cyton Base
==========
"""

import re
import time
import logging
import pickle
from threading import Thread
from datetime import datetime
from functools import cached_property
from abc import ABCMeta, abstractmethod
from multiprocessing import Process, Manager
from typing import Optional, Union, Literal, Dict, List, TypeVar, Any

import numpy as np
from kafka import KafkaConsumer

from .binary_stream import BinaryStream
from ..utils import HDF5Writer, interpolate_datetime

DAISY = Literal['auto', True, False]
QUEUE = TypeVar('Queue')


########################################################################
class CytonConstants:
    """Default constants defined in the `Cyton SDK <https://docs.openbci.com/docs/02Cyton/CytonSDK>`_"""

    VREF = 4.5

    BIN_HEADER = 0xa0

    VERSION = b'V'
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

    AD1299_GAIN_REGISTER = {
        '000': 1,
        '001': 2,
        '010': 4,
        '011': 6,
        '100': 8,
        '101': 12,
        '110': 24,
    }

    # ----------------------------------------------------------------------
    def __init__(self) -> None:
        """"""


########################################################################
class CytonBase(CytonConstants, metaclass=ABCMeta):
    """
    The Cyton data format and SDK define all interactions and capabilities of
    the board, the full instructions can be found in the official documentation.

      * https://docs.openbci.com/Hardware/03-Cyton_Data_Format
      * https://docs.openbci.com/OpenBCI%20Software/04-OpenBCI_Cyton_SDK

    daisy
        Daisy board can be detected on runtime or declare it specifically.
    montage
        A list means consecutive channels e.g. `['Fp1', 'Fp2', 'F3', 'Fz',
        'F4']` and a dictionary means specific channels `{1: 'Fp1', 2: 'Fp2',
        3: 'F3', 4: 'Fz', 5: 'F4'}`.
    streaming_package_size
        The streamer will try to send packages of this size, this is NOT the
        sampling rate for data acquisition.
    capture_stream
        Indicates if the data from the stream will be captured in asynchronous
        mode.
    """

    # ----------------------------------------------------------------------
    def __init__(self, daisy: DAISY, montage: Optional[Union[list, dict]],
                 streaming_package_size: int, capture_stream: bool) -> None:
        """"""
        # Default sample rate for serial and wifi mode
        self.sample_rate = 250

        # Daisy before Montage
        if daisy in [True, False]:
            self.daisy = daisy
        elif daisy == 'auto':
            self.daisy = self.daisy_attached()

        # Montage
        self.montage = montage

        # Data Structure with special queue that can live across process
        self._data_eeg = Manager().Queue()
        self._data_aux = Manager().Queue()
        self._data_markers = Manager().Queue()
        self._data_timestamp = Manager().Queue()

        self.reset_input_buffer()
        self._auto_capture_stream = capture_stream
        self.streaming_package_size = streaming_package_size

    # ----------------------------------------------------------------------
    @property
    def boardmode(self) -> str:
        """Stop stream and ask for the current boardmode."""

        self.command(self.STOP_STREAM)
        response = self.command(self.BOARD_MODE_GET)

        for mode in [b'analog', b'digital', b'debug', b'default', b'marker']:
            if mode in response:
                return mode.decode()

        logging.warning(
            'Stream must be stoped for read the current boardmode')

    # ----------------------------------------------------------------------
    @property
    def montage(self) -> Union[List, Dict]:
        """The current montage configured on initialization."""
        return self._montage

    # ----------------------------------------------------------------------
    @montage.setter
    def montage(self, montage: Union[List, Dict, None]) -> None:
        """Define the information with que electrodes names.

        A list means consecutive channels e.g. `['Fp1', 'Fp2', 'F3', 'Fz',
        'F4']` and a dictionary means specific channels `{1: 'Fp1', 2: 'Fp2',
        3: 'F3', 4: 'Fz', 5: 'F4'}`. Internally the montage is always a
        dictionary.

        Parameters
        ----------
        montage :
            Object for generate the montage parameter.
        """

        if isinstance(montage, (bytes)):
            montage = pickle.loads(montage)

        if isinstance(montage, (list, tuple, range)):
            self._montage = {i: ch for i, ch in enumerate(montage)}
        elif isinstance(montage, (dict)):
            self._montage = {i: ch for i, ch in enumerate(montage.values())}
        else:
            # Default
            if self.daisy:
                self._montage = {i: f'ch{i+1}' for i in range(16)}
            elif not self.daisy:
                self._montage = {i: f'ch{i+1}' for i in range(8)}

    # ----------------------------------------------------------------------
    def deactivate_channel(self, channels: List[int]) -> None:
        """Deactivate the channels specified.

        Parameters
        ----------
        channels :
            1-based indexing channels.
        """

        chain = ''.join([chr(self.DEACTIVATE_CHANEL[ch - 1])
                         for ch in channels]).encode()
        self.command(chain)

    # ----------------------------------------------------------------------
    def activate_channel(self, channels: List[int]) -> None:
        """Activate the channels specified.

        Parameters
        ----------
        channels :
            1-based indexing channels.
        """

        chain = ''.join([chr(self.ACTIVATE_CHANEL[ch - 1])
                         for ch in channels]).encode()
        self.command(chain)

    # ----------------------------------------------------------------------
    def command(self, c: Union[str, bytes]) -> str:
        """Send a command to device.

        Before send the commmand the input buffer is cleared, and after that
        waits 300 ms for a response. Is possible to send a raw bytes, a
        `CytonConstants` attribute or the constant name e.g.

        >>> comand(b'~4')
        >>> command(CytonConstants.SAMPLE_RATE_1KSPS)
        >>> command('SAMPLE_RATE_1KSPS')

        Parameters
        ----------
        c
            Command to send.

        Returns
        -------
        str
            If the command generate a response this will be returned.
        """

        if hasattr(self, c.decode()):
            c = getattr(self, c.decode())

        if c in list(self.SAMPLE_RATE_VALUE.keys()):
            self.sample_rate = int(self.SAMPLE_RATE_VALUE[c])

        self.reset_input_buffer()
        self.write(c)
        time.sleep(0.3)
        response = self.read(2**11)
        logging.info(f'Writing: {c}')
        if response and len(response) > 100:
            logging.info(f'Response: {response[:100]}...')
        else:
            logging.info(f'Response: {response}')

        if response and hasattr(response, 'encode'):
            response = response.encode()
        elif response and isinstance(response, (list)):
            response = ''.join([chr(r) for r in response]).encode()

        return response

    # ----------------------------------------------------------------------
    def channel_settings(self, channels: List[int],
                         power_down: Optional[bytes] = CytonConstants.POWER_DOWN_ON,
                         gain: Optional[bytes] = CytonConstants.GAIN_24,
                         input_type: Optional[bytes] = CytonConstants.ADSINPUT_NORMAL,
                         bias: Optional[bytes] = CytonConstants.BIAS_INCLUDE,
                         srb2: Optional[bytes] = CytonConstants.SRB2_CONNECT,
                         srb1: Optional[bytes] = CytonConstants.SRB1_DISCONNECT) -> None:
        """Channel Settings commands.

        Parameters
        ----------
        channels
            1-based indexing channels list that will share the configuration
            specified.
        power_down
            `POWER_DOWN_ON` (default), `POWER_DOWN_OFF`.
        gainoptional
            `GAIN_24` (default), `GAIN_12`, `GAIN_8`, `GAIN_6`, `GAIN_4`,
            `GAIN_2`, `GAIN_1`.
        input_type
            Select the ADC channel input source: `ADSINPUT_NORMAL` (default),
            `ADSINPUT_SHORTED`, `ADSINPUT_BIAS_MEAS`, `ADSINPUT_MVDD`,
            `ADSINPUT_TEMP`, `ADSINPUT_TESTSIG`, `ADSINPUT_BIAS_DRP`,
            `ADSINPUT_BIAS_DRN`,
        bias
            Select to include the channel input in BIAS generation:
            `BIAS_INCLUDE` (default), `BIAS_REMOVE`.
        srb2
            Select to connect this channel’s P input to the SRB2 pin. This
            closes a switch between P input and SRB2 for the given channel, and
            allows the P input also remain connected to the ADC: `SRB2_CONNECT`
            (default), `SRB2_DISCONNECT`.
        srb1
            Select to connect all channels’ N inputs to SRB1. This effects all
            pins, and disconnects all N inputs from the ADC: `SRB1_DISCONNECT`
            (default), `SRB1_CONNECT`.


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

        self.reset_input_buffer()

        start = b'x'
        end = b'X'
        chain = b''
        for ch in channels:
            ch = chr(self.CHANNEL_SETTING[ch - 1]).encode()
            chain += b''.join([start, ch, power_down, gain, input_type, bias,
                               srb2, srb1, end])

        self.command(chain)

    # ----------------------------------------------------------------------
    def leadoff_impedance(self, channels: List[int],
                          pchan: Optional[bytes] = CytonConstants.TEST_SIGNAL_NOT_APPLIED,
                          nchan: Optional[bytes] = CytonConstants.TEST_SIGNAL_APPLIED) -> None:
        """LeadOff Impedance Commands

        Parameters
        ----------
        channels
            1-based indexing channels list that will share the configuration
            specified.
        pchan
            `TEST_SIGNAL_NOT_APPLIED` (default), `TEST_SIGNAL_APPLIED`.
        nchan
            `TEST_SIGNAL_APPLIED` (default), `TEST_SIGNAL_NOT_APPLIED`.


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

    # ----------------------------------------------------------------------
    def send_marker(self, marker: Union[str, bytes, int], burst: int = 4) -> None:
        """Send marker to device.

        The marker sended will be added to the `AUX` bytes in the next data
        input.

        The OpenBCI markers does not work as well as expected, so this module
        implement an strategy for make it works. A burst markers are sended but
        just one are readed, this add a limitation: No more that one marker each
        300 ms are permitted.

        Parameters
        ----------
        marker
            A single value with the desired marker. Only can be a capitalized
            letter, or an integer between 65 and 90. These limitations are
            imposed by this library and not by the SDK
        burst
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
    def daisy_attached(self) -> bool:
        """Check if a Daisy module is attached.

        This command will activate the Daisy module is this is available.

        Returns
        -------
        bool
            Daisy module activated.

        """
        response = self.command(self.USE_16CH_ONLY)
        if not response:
            return self.daisy_attached()

        daisy = not (('no daisy to attach' in response.decode(errors='ignore')) or
                     ('8' in response.decode(errors='ignore')))

        return daisy

    # ----------------------------------------------------------------------
    def capture_stream(self) -> None:
        """Create a process for connecting to the stream and capture data from it."""

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

                        timestamp = np.zeros(message.value['context']['samples'])
                        timestamp[-1] = message.value['context']['created']
                        self._data_timestamp.put(timestamp)

                    elif message.topic == 'marker':

                        timestamp = message.value['timestamp']
                        marker = message.value['marker']
                        self._data_markers.put((timestamp, marker))

        self.persistent_process = Process(target=bulk_buffer)
        self.persistent_process.start()

    # ----------------------------------------------------------------------
    def start_stream(self) -> None:
        """Create the binary stream channel."""
        self.binary_stream = BinaryStream(self.streaming_package_size)

        self.reset_buffers()
        self.reset_input_buffer()

        if self._auto_capture_stream:
            self.capture_stream()

    # ----------------------------------------------------------------------
    def stop_stream(self) -> None:
        """Stop the acquisition daemon if exists."""
        if hasattr(self, 'persistent_process'):
            self.persistent_process.terminate()
            self.persistent_process.join()

    # ----------------------------------------------------------------------
    @abstractmethod
    def close(self):
        """Stops data stream."""

    # ----------------------------------------------------------------------
    @abstractmethod
    def write(self):
        """Write bytes."""

    # ----------------------------------------------------------------------
    @abstractmethod
    def read(self):
        """Read binary data."""

    # ----------------------------------------------------------------------
    def reset_input_buffer(self):
        """Flush input data."""

    # ----------------------------------------------------------------------
    @property
    def eeg_buffer(self) -> QUEUE:
        """Return the deserialized data buffer for EEG."""
        return self._data_eeg

    # ----------------------------------------------------------------------
    @property
    def timestamp_buffer(self) -> QUEUE:
        """Return the deserialized data buffer for timestamps."""
        return self._data_timestamp

    # ----------------------------------------------------------------------
    @property
    def markers_buffer(self) -> QUEUE:
        """Return the deserialized data buffer for markers."""
        return self._data_markers

    # ----------------------------------------------------------------------
    @property
    def aux_buffer(self) -> QUEUE:
        """Return the deserialized data buffer for auxiliar data."""
        return self._data_aux

    # ----------------------------------------------------------------------
    @cached_property
    def eeg_time_series(self) -> np.ndarray:
        """Return data acquired in shape (`channels, time`)."""

        eeg = [self._data_eeg.get() for _ in range(self._data_eeg.qsize())]
        if eeg:
            eeg = np.concatenate(eeg, axis=1)
            return eeg

        logging.warning(
            f'No EEG data captured, make sure to activate `capture_stream` in the {self} instantiation\n'
            f'This too could be because the `stream_eeg` daemon was not running.')
        return np.array([])

    # ----------------------------------------------------------------------
    @cached_property
    def aux_time_series(self) -> np.ndarray:
        """Return auxiliar data acquired in shape (`AUX, time`)."""

        aux = [self._data_aux.get() for _ in range(self._data_aux.qsize())]
        try:
            aux = np.concatenate(aux, axis=1)
        except np.AxisError:
            aux = np.concatenate(aux, axis=0)

        return aux

    # ----------------------------------------------------------------------
    @cached_property
    def timestamp_time_series(self) -> np.ndarray:
        """Return timestamps acquired.

        Since there is only one timestamp for package, the others values are
        interpolated.
        """

        timestamp = [self._data_timestamp.get() for _ in range(self._data_timestamp.qsize())]
        timestamp = np.concatenate(timestamp, axis=0)
        length = self.eeg_time_series.shape[1]
        sample_rate = self.sample_rate

        timestamp = interpolate_datetime(timestamp, length)

        return timestamp

    # ----------------------------------------------------------------------
    @cached_property
    def markers(self) -> Dict[str, list]:
        """Return a dictionary with markes as keys and a list of timestamps as
        values e.g

        >>> {'LEFT': [1603150888.752062, 1603150890.752062, 1603150892.752062],
             'RIGHT': [1603150889.752062, 1603150891.752062, 1603150893.752062],}
        """

        markers = {}
        for t, marker in [self._data_markers.get() for _ in range(self._data_markers.qsize())]:
            markers.setdefault(marker, []).append(t)

        return markers

    # ----------------------------------------------------------------------
    def reset_buffers(self) -> None:
        """Discard buffers."""

        for buffer in [self._data_eeg,
                       self._data_aux,
                       self._data_markers,
                       self._data_timestamp,
                       ]:

            try:
                with buffer.mutex:
                    buffer.clear()
            except AttributeError:
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
    def stream(self, duration: int) -> None:
        """Start a synchronous process for start stream data.

        This call will hangs until durations be completed.

        Parameters
        ----------
        duration
            Seconds for data collection.
        """

        self.start_stream()
        time.sleep(duration)
        self.stop_stream()

    # ----------------------------------------------------------------------
    def listen_stream_markers(self, host: Optional[str] = 'localhost',
                              topics: Optional[List[str]] = ['markers']) -> None:
        """Redirect markers form Kafka stream to board, this feature needs
        `markers` boardmode configured."""

        bootstrap_servers = [f'{host}:9092']

        markers_consumer = KafkaConsumer(
            bootstrap_servers=bootstrap_servers,
            value_deserializer=pickle.loads,
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

        self.stream_markers = Thread(target=_send_marker)
        self.stream_markers.start()

    # ----------------------------------------------------------------------
    def save(self, filename: str, montage_name: str,
             sample_rate: Optional[int] = None) -> None:
        """Create a hdf file with acquiered data.

        Parameters
        ----------
        filename
            Path with the destination of the hdf file.
        montage_name
            Montage name for MNE e.g 'standard_1020'.
        sample_rate
            The sampling rate for acquired data.

        """
        if sample_rate is None:
            sample_rate = self.sample_rate

        header = {'sample_rate': sample_rate,
                  'datetime': datetime.now().timestamp(),
                  'montage': montage_name,
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

            if bool(self.markers):
                logging.info(f'Writed {self.markers.keys()} markers')

    # ----------------------------------------------------------------------
    def __getattribute__(self, attr: str) -> Any:
        """Some attributes must be acceded from RPyC."""

        if super().__getattribute__('remote_host'):
            return getattr(super().__getattribute__('remote_host'), attr)

        return super().__getattribute__(attr)
