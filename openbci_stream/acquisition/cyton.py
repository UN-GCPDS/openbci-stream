"""
=====
Cyton
=====

The OpenBCI Cyton PCBs were designed with Design Spark, a free PCB capture
program.


Cyton Board Specs:

* Power with 3-6V DC Battery ONLY
* PIC32MX250F128B Micrcontroller with chipKIT UDB32-MX2-DIP bootloader
* ADS1299 Analog Front End
* LIS3DH 3 axis Accelerometer
* RFduino BLE radio
* Micro SD card slot
* Voltage Regulation (3V3, +2.5V, -2.5V)
* Board Dimensions 2.41 x 2.41 (octogon has 1 edges) [inches]
* Mount holes are 1/16 ID, 0.8 x 2.166 on center [inches]


Data Format
===========

Binary Format
-------------

+-------------+----------------------------------------------------------------+
| **Byte No** | **Description**                                                |
+-------------+----------------------------------------------------------------+
| 1           | Start byte, always `0xA0`                                      |
+-------------+----------------------------------------------------------------+
| 2           | Sample Number                                                  |
+-------------+----------------------------------------------------------------+
| 3-26        | EEG Data, values are 24-bit signed, MSB first                  |
+-------------+----------------------------------------------------------------+
| 27-32       | Aux Data                                                       |
+-------------+----------------------------------------------------------------+
| 33          | Footer, `0xCX` where `X` is 0-F in hex                         |
+-------------+----------------------------------------------------------------+



EEG Data for 8 channels
-----------------------

24-Bit Signed.

+-------------+----------------------------------------------------------------+
| **Byte No** | **Description**                                                |
+-------------+----------------------------------------------------------------+
| 3-5         | Data value for EEG channel 1                                   |
+-------------+----------------------------------------------------------------+
| 6-8         | Data value for EEG channel 2                                   |
+-------------+----------------------------------------------------------------+
| 9-11        | Data value for EEG channel 3                                   |
+-------------+----------------------------------------------------------------+
| 12-14       | Data value for EEG channel 4                                   |
+-------------+----------------------------------------------------------------+
| 15-17       | Data value for EEG channel 5                                   |
+-------------+----------------------------------------------------------------+
| 18-20       | Data value for EEG channel 6                                   |
+-------------+----------------------------------------------------------------+
| 21-23       | Data value for EEG channel 7                                   |
+-------------+----------------------------------------------------------------+
| 24-26       | Data value for EEG channel 8                                   |
+-------------+----------------------------------------------------------------+


EEG Data for 16 channels
------------------------

24-Bit Signed.

+----------------------------+--------------------------+--------------------------+
| **Received**               | **Upsampled board data** | **Upsampled daisy data** |
+--------------+-------------+--------------------------+--------------------------+
| sample(3)    |             | avg(sample(1),sample(3)) | sample(2)                |
+--------------+-------------+--------------------------+--------------------------+
|              | sample(4)   | sample(3)                | avg(sample(2),sample(4)) |
+--------------+-------------+--------------------------+--------------------------+
| sample(5)    |             | avg(sample(3),sample(5)) | sample(4)                |
+--------------+-------------+--------------------------+--------------------------+
|              | sample(6)   | sample(5)                | avg(sample(4),sample(6)) |
+--------------+-------------+--------------------------+--------------------------+
| sample(7)    |             | avg(sample(5),sample(7)) | sample(7)                |
+--------------+-------------+--------------------------+--------------------------+
|              | sample(8)   | sample(7)                | avg(sample(6),sample(8)) |
+--------------+-------------+--------------------------+--------------------------+

This transmission only applies to Cyton + Daisy and RFduino, if WiFi shield is
used then all data is transmitted, and is not necessary to interpolate.


Aux Data
--------

16-Bit Signed.

+--------------------+-------------+-------------+-------------+-------------+-------------+-------------+-------------------------------+
| **Stop Byte (33)** | **Byte 27** | **Byte 28** | **Byte 29** | **Byte 30** | **Byte 31** | **Byte 32** |          **Name**             |
+--------------------+-------------+-------------+-------------+-------------+-------------+-------------+-------------------------------+
| 0xc0               | AX1         | AX2         | AY1         | AY2         | AZ1         | AZ2         | Standard with accel           |
+--------------------+-------------+-------------+-------------+-------------+-------------+-------------+-------------------------------+
| 0xC1               | UDF         | UDF         | UDF         | UDF         | UDF         | UDF         | Standard with raw aux         |
+--------------------+-------------+-------------+-------------+-------------+-------------+-------------+-------------------------------+
| 0xC2               | UDF         | UDF         | UDF         | UDF         | UDF         | UDF         | User defined                  |
+--------------------+-------------+-------------+-------------+-------------+-------------+-------------+-------------------------------+
| 0xC3               | *AC*        | *AV*        | T3          | T2          | T1          | T0          | Time stamped set with accel   |
+--------------------+-------------+-------------+-------------+-------------+-------------+-------------+-------------------------------+
| 0xC4               | *AC*        | *AV*        | T3          | T2          | T1          | T0          | Time stamped with accel       |
+--------------------+-------------+-------------+-------------+-------------+-------------+-------------+-------------------------------+
| 0xC5               | UDF         | UDF         | T3          | T2          | T1          | T0          | Time stamped set with raw aux |
+--------------------+-------------+-------------+-------------+-------------+-------------+-------------+-------------------------------+
| 0xC6               | UDF         | UDF         | T3          | T2          | T1          | T0          | Time stamped with raw aux     |
+--------------------+-------------+-------------+-------------+-------------+-------------+-------------+-------------------------------+


Aux Data
--------

16-Bit Signed.

+-------------+-------------+
| **Byte 27** | **Byte 28** |
+-------------+-------------+
|  X          | AX1         |
+-------------+-------------+
|  x          | AX0         |
+-------------+-------------+
|  Y          | AY1         |
+-------------+-------------+
|  y          | AY0         |
+-------------+-------------+
|  Z          | AZ1         |
+-------------+-------------+
|  z          | AZ0         |
+-------------+-------------+
"""

import os
import sys
import time
import types
import pickle
import socket
import logging
import asyncore
from threading import Thread
from typing import Optional, Union, Literal, Dict, List, Any

from .cyton_base import CytonBase
from .tcp_server import WiFiShieldTCPServer

import rpyc
import serial
import requests

DEFAULT_LOCAL_IP = "192.168.1.1"

MODE = Literal['serial', 'wifi', None]
DAISY = Literal['auto', True, False]


########################################################################
class CytonRFDuino(CytonBase):
    """
    RFduino is the default communication mode for Cyton, this set a
    serial comunication through a USB dongle with a sample frequency of `250`
    Hz, for 8 or 16 channels.

    Parameters
    ----------
    port
        Serial port.
    host
        IP address for the server that has the OpenBCI board attached, by
        default its assume that is the same machine where is it executing, this
        is the `localhost`.
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
    def __init__(self, port: Optional = None, host: Optional[str] = None,
                 daisy: DAISY = 'auto',
                 montage: Optional[Union[list, dict]] = None,
                 streaming_package_size: int = 250,
                 capture_stream: bool = False,
                 board_id: str = '0',
                 parallel_boards: int = 1,
                 ) -> None:
        """"""

        self.remote_host = None
        self._markers = None

        if host == 'localhost':
            host = None

        if host:
            try:
                rpyc_service = rpyc.connect(host, 18861, config={
                    'allow_public_attrs': True,
                    'allow_pickle': True,
                })
                self.remote_host = getattr(rpyc_service.root, self.__class__.__name__)(
                    port,
                    host=None,
                    daisy=daisy,
                    capture_stream=capture_stream,
                    montage=pickle.dumps(montage),
                    streaming_package_size=streaming_package_size,
                    board_id=board_id,
                    parallel_boards=parallel_boards,
                )
            except socket.gaierror:
                logging.error("'openbci_rpyc' daemon are running?")

            return

        if port is None:
            port = self._get_serial_ports()
            if port:
                logging.info(f"Port {port} found.")

        if port is None:
            logging.error("No device was auto detected.")
            sys.exit()

        self.device = serial.Serial(port, 115200, timeout=0.3,
                                    write_timeout=0.01,
                                    parity=serial.PARITY_NONE,
                                    stopbits=serial.STOPBITS_ONE)

        super().__init__(daisy, montage, streaming_package_size,
                         capture_stream, board_id, parallel_boards)

    # ----------------------------------------------------------------------
    def _get_serial_ports(self) -> Optional[str]:
        """Look for first available serial port.

        Returns
        -------
        str
            String with the port name or `None` if no ports were founded.
        """

        if os.name == 'nt':
            prefix = ('COM{}')
        elif os.name == 'posix':
            prefix = ('/dev/ttyACM{}', '/dev/ttyUSB{}')

        for pref in prefix:
            for i in range(20):
                port = pref.format(i)
                try:
                    d = serial.Serial(port, timeout=0.2)
                    if d.write(self.START_STREAM):
                        d.close()
                        return port
                except Exception as e:
                    logging.warning(e)
                    continue

    # ----------------------------------------------------------------------
    def read(self, size: int) -> bytes:
        """Read size bytes from the serial port.

        Parameters
        ----------
        size
            Size of input buffer.

        Returns
        -------
        read
            Data read.
        """

        try:
            return self.device.read(size)
        except Exception as e:
            # If there is no data yet, call again
            logging.warning(e)
            return self.read(size)

    # ----------------------------------------------------------------------
    def write(self, data: bytes) -> None:
        """Write the given data over the serial port."""
        self.device.write(data)

    # ----------------------------------------------------------------------
    def close(self):
        """Close the serial communication."""
        self.stop_stream()
        self.device.close()
        super().close()

    # ----------------------------------------------------------------------
    def _stream_data(self, size: Optional[int] = 2**8,
                     kafka_context: Optional[Dict] = {}) -> None:
        """Write binary raw into a kafka producer.

        This method will feed the producer while the serial device has data to
        be read.

        Parameters
        ----------
        size
            The buffer length to read.
        kafka_context
            Information from the acquisition side useful for deserializing and
            that will be packaged back in the stream.
        """

        while binary := self.read(size):
            try:
                # kafka_context.update({'created': datetime.now().timestamp()})
                data = {'context': kafka_context,
                        'data': binary,
                        }
                self.binary_stream.stream(data)
            except serial.SerialException as e:
                logging.error(e)

    # ----------------------------------------------------------------------
    def start_stream(self) -> None:
        """Initialize a Thread for reading data from the serial port and
        streaming into a Kafka producer.
        """

        kafka_context = {'daisy': self.daisy,
                         'boardmode': self.boardmode,
                         'montage': self.montage,
                         'connection': 'serial',
                         'gain': self._get_gain(),
                         'parallel_boards': self.parallel_boards,
                         }

        self.command(self.START_STREAM)
        super().start_stream()

        # Thread for read data
        if hasattr(self, "thread_data_collect") and self.thread_data_collect.isAlive():
            pass
        else:
            self.thread_data_collect = Thread(target=self._stream_data,
                                              args=(2**8, kafka_context))
            self.thread_data_collect.start()

    # ----------------------------------------------------------------------
    def stop_stream(self) -> None:
        """Stop the data collection that runs asynchronously."""
        self.command(self.STOP_STREAM)
        super().stop_stream()
        self.binary_stream.close()

    # ----------------------------------------------------------------------
    def reset_input_buffer(self):
        """Clear input buffer, discarding all that is in the buffer."""
        self.device.reset_input_buffer()
        self.device.flushInput()

    # ----------------------------------------------------------------------
    def _get_gain(self) -> list:
        """Return the gains from ADS1299 register.

        As defined in the `datasheet <https://www.ti.com/lit/ds/symlink/ads1299.pdf?ts=1604333779995&ref_url=https%253A%252F%252Fwww.google.com%252F>`_
        """

        default = 24
        response = self.command(self.QUERY_REGISTER)
        registers = {reg.split(',')[0]: reg.split(',')[1:]
                     for reg in filter(None, response.decode().split('\n'))}
        gains = [self.AD1299_GAIN_REGISTER.get(''.join(registers.get(
            f'CH{i}SET', '')[3:6]).replace(' ', ''), default) for i in range(1, 9)]
        return gains


########################################################################
class CytonWiFi(CytonBase):
    """
    This module implement a TCP connection for the WiFi module with a sample
    frequency from `250` Hz up to 16 kHz, for 8 or 16 channels (8 kHz for 16
    channels).

    Parameters
    ----------
    ip_address
        IP addres for the WiFi shield.
    host
        IP address for the server that has the OpenBCI board attached, by
        default its assume that is the same machine where is it executing, this
        is the `localhost`.
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
    def __init__(self, ip_address: str, host: str = None, daisy: DAISY = 'auto',
                 montage: Optional[Union[list, dict]] = None,
                 streaming_package_size: int = 250,
                 capture_stream: Optional[bool] = False,
                 board_id: str = '0',
                 parallel_boards: int = 1, ) -> None:
        """"""
        self.remote_host = None

        self._ip_address = ip_address
        self._readed = None
        self._local_ip_address = self._get_local_ip_address()

        if host == 'localhost':
            host = None

        if host:
            try:
                rpyc_service = rpyc.connect(host, 18861, config={
                    'allow_public_attrs': True,
                    'allow_pickle': True,
                })
                self.remote_host = getattr(rpyc_service.root, self.__class__.__name__)(
                    self._ip_address,
                    host=None,
                    daisy=daisy,
                    capture_stream=capture_stream,
                    montage=pickle.dumps(montage),
                    streaming_package_size=streaming_package_size,
                    board_id=board_id,
                    parallel_boards=parallel_boards,
                )
            except socket.gaierror:
                logging.error("'openbci_rpyc' daemon are running?")

            return

        super().__init__(daisy, montage, streaming_package_size,
                         capture_stream, board_id, parallel_boards)

        self._create_tcp_server()
        time.sleep(5)  # secure delay
        self._start_tcp_client()

        self._start_loop()

    # ----------------------------------------------------------------------
    def _get_local_ip_address(self) -> str:
        """Get the current network IP assigned."""

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip_address = s.getsockname()[0]
            s.close()
            return local_ip_address

        except Exception as e:
            logging.warning('Impossible to detect a network connection, the WiFi'
                            'module and this machine must share the same network.')
            logging.warning(f'If you are using this machine as server (access point) '
                            f'the address {DEFAULT_LOCAL_IP} will be used.')
            logging.warning(e)

            return DEFAULT_LOCAL_IP

    # ----------------------------------------------------------------------
    def write(self, data: Union[str, bytes]) -> None:
        """Send command to board through HTTP protocole.

        Parameters
        ----------
        data :
            Commands to send, It should not be more than 31 characters long.
        """

        if hasattr(data, 'decode'):
            data = data.decode()
        elif isinstance(data, int):
            data = chr(data)

        response = None
        try:
            logging.info(f"Sending command: '{data}'")
            response = requests.post(
                f"http://{self._ip_address}/command", json={'command': data})
        except requests.exceptions.ConnectionError as msg:
            if 'Connection aborted' in str(msg):
                time.sleep(0.3)
                return self.write(data)
        except Exception as msg:
            logging.warning(f"Error on sending command '{data}':{msg}")
            return

        if response and response.status_code == 200:
            self._readed = response.text
        elif response and response.status_code == 502:
            logging.info(f"No confirmation from board, does not mean fail.")
        else:
            if response:
                logging.warning(
                    f"Error code: {response.status_code} {response.text}")
            self._readed = None

    # ----------------------------------------------------------------------
    def read(self, size=None) -> bytes:
        """Read the response for some command.

        Unlike serial mode, over WiFi there is not read and write individual
        commands, the response is got in the same write command. This
        implementation tries to emulate the the behavior of serial read/write
        for compatibility reasons. Not all command return a response.
        """

        time.sleep(0.2)  # critical dealy for wait a response.
        return self._readed

    # ----------------------------------------------------------------------
    def start_stream(self) -> None:
        """Initialize a TCP client on the WiFi shield and sends the command to
        starts stream."""

        super().start_stream()
        # self._start_tcp_client()

        response = requests.get(f"http://{self._ip_address}/stream/start")
        if response.status_code != 200:
            logging.warning(
                f"Unable to start streaming.\nCheck API for status code {response.status_code} on /stream/start")

    # ----------------------------------------------------------------------
    def stop_stream(self) -> None:
        """Stop the data collection that runs asynchronously and sends the
        command to stops stream."""

        super().stop_stream()

        response = requests.get(f"http://{self._ip_address}/stream/stop")
        if response.status_code != 200:
            logging.warning(
                f"Unable to stop streaming.\nCheck API for status code {response.status_code} on /stream/stop")

        self.binary_stream.close()
        asyncore.close_all()

    # ----------------------------------------------------------------------
    def kafka_context(self) -> Dict[str, Any]:
        """Kafka contex generator."""
        return {
            'daisy': self.daisy,
            'boardmode': self.boardmode,
            'montage': self.montage,
            'connection': 'wifi',
            'gain': self._gain,
            'parallel_boards': self.parallel_boards,
        }

    # ----------------------------------------------------------------------
    def _create_tcp_server(self) -> None:
        """Create TCP server, this server will handle the streaming EEG data."""

        # kafka_context = {
            # 'daisy': self.daisy,
            # 'boardmode': self.boardmode,
            # 'montage': self.montage,
            # 'connection': 'wifi',
        # }

        self.local_wifi_server = WiFiShieldTCPServer(self._local_ip_address,
                                                     lambda: getattr(
                                                         self, 'binary_stream'),
                                                     self.kafka_context,
                                                     )
        self.local_wifi_server_port = self.local_wifi_server.socket.getsockname()[
            1]
        logging.info(
            f"Open socket on {self._local_ip_address}:{self.local_wifi_server_port}")

    # ----------------------------------------------------------------------
    def _start_tcp_client(self):
        """Connect the board to the TCP server. Sends configuration of the
        previously server created to the board, so they can connected to.
        """

        if self._ip_address is None:
            raise ValueError('self._ip_address cannot be None')

        logging.info(f"Init WiFi connection with IP: {self._ip_address}")

        self.requests_session = requests.Session()
        response = requests.get(f"http://{self._ip_address}/board")

        if response.status_code == 200:
            board_info = response.json()

            if not board_info['board_connected']:
                raise RuntimeError("No board connected to WiFi Shield.")
            self._gain = board_info['gains']
            self.local_wifi_server.set_gain(self._gain)

        # res_tcp_post = requests.post(f"http://{self._ip_address}/tcp",
                                     # json={
                                        # 'ip': self._local_ip_address,
                                        # 'port': self.local_wifi_server_port,
                                        # 'output': 'json',
                                        # 'delimiter': True,
                                        # 'latency': 1000,
                                         # })
        res_tcp_post = requests.post(f"http://{self._ip_address}/tcp",
                                     json={
                                        'ip': self._local_ip_address,
                                        'port': self.local_wifi_server_port,
                                        'output': 'raw',
                                        'latency': 1000,
                                         })
        if res_tcp_post.status_code == 200:
            tcp_status = res_tcp_post.json()
            if tcp_status['connected']:
                logging.info("WiFi Shield to Python TCP Socket Established")
            else:
                raise RuntimeWarning(
                    "WiFi Shield is not able to connect to local server.")

        else:
            logging.warning(
                f"status_code {res_tcp_post.status_code}:{res_tcp_post.reason}")

    # ----------------------------------------------------------------------
    def set_latency(self, latency: int) -> None:
        """"""
        response = None
        try:
            response = requests.post(
                f"http://{self._ip_address}/latency", json={'latency': latency, })
        except Exception as e:
            logging.warning(f"Error on setting latency '{data}': {e}")
            return

        if response:
            if response.status_code == 200:
                return
            logging.warning(
                f"Error code: {response.status_code} {response.text}")

    # ----------------------------------------------------------------------
    def close(self) -> None:
        """Stops TCP server and data acquisition."""
        self.stop_stream()
        requests.delete(f"http://{self._ip_address}/tcp")
        super().close()

    # ----------------------------------------------------------------------
    def _start_loop(self):
        """Start the TCP server on a thread asyncore loop."""
        self.th_loop = Thread(target=asyncore.loop, args=(), )
        self.th_loop.start()


# ########################################################################
# class CytonR:
    # """"""

    # # ----------------------------------------------------------------------
    # def __init__(self, mode: MODE, endpoint: Union[str, List] = None, host: str = None,
                 # daisy: DAISY = 'auto',
                 # montage: Optional[Union[list, dict]] = None,
                 # streaming_package_size: int = 250,
                 # capture_stream: Optional[bool] = False,
                 # number_of_channels: List = [],
                 # ) -> Union[CytonRFDuino, CytonWiFi]:
        # """"""

        # if host == 'localhost':
            # host = None

        # if host:
            # rpyc_service = rpyc.connect(host, 18861, config={
                # 'allow_public_attrs': True,
                # 'allow_pickle': True,
            # })
            # self.remote_host = getattr(rpyc_service.root, 'Cyton')(
                # mode,
                # endpoint,
                # host=None,
                # daisy=daisy,
                # montage=pickle.dumps(montage),
                # streaming_package_size=streaming_package_size,
                # capture_stream=capture_stream,
                # number_of_channels=number_of_channels,
            # )

    # # ----------------------------------------------------------------------
    # def __getattribute__(self, attr: str) -> Any:
        # """Some attributes must be acceded from RPyC."""

        # if super().__getattribute__('remote_host'):
            # return getattr(super().__getattribute__('remote_host'), attr)

        # return super().__getattribute__(attr)


# ----------------------------------------------------------------------
def wifi(host, ip):
    """"""
    rpyc_service = rpyc.connect(host, 18861, config={
        'allow_public_attrs': True,
        'allow_pickle': True,
    })
    return rpyc_service.root.Wifi(ip)


# ----------------------------------------------------------------------
def restart_services(host):
    """"""
    rpyc_service = rpyc.connect(host, 18861, config={
        'allow_public_attrs': True,
        'allow_pickle': True,
    })
    return rpyc_service.root.RestartServices()


########################################################################
class Cyton:
    """
    `Cyton` is a shortcut for `CytonRFDuino` or `CytonWiFi`:

    >>> Cyton('serial', ...)

    is equals to:

    >>> CytonRFDuino(...)

    and

    >>> Cyton('wifi', ...)

    the same that do:

    >>> CytonWiFi(...)

    Parameters
    ----------
    mode
        `serial` or `wifi`
    endpoint
        Serial port for RFduino or IP address for WiFi module.
    host
        IP address for the server that has the OpenBCI board attached, by
        default its assume that is the same machine where is it executing, this
        is the `localhost`.
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
    def __init__(self, mode: MODE, endpoint: Union[str, List] = None, host: str = None,
                 daisy: Optional[List[DAISY]] = None,
                 montage: Optional[Union[list, dict]] = None,
                 streaming_package_size: int = 250,
                 capture_stream: Optional[bool] = False,
                 number_of_channels: List = [],
                 ) -> Union[CytonRFDuino, CytonWiFi]:

        if isinstance(endpoint, str):
            endpoint = [endpoint]

        if host == 'localhost':
            host = None

        if daisy is None:
            daisy = [False for _ in endpoint]
        elif isinstance(daisy, bool):
            daisy = [daisy]

        self.remote_host = None
        self.openbci = None
        if host:
            self.openbci = None
            rpyc_service = rpyc.connect(host, 18861, config={
                'allow_public_attrs': True,
                'allow_pickle': True,
            })
            self.remote_host = getattr(rpyc_service.root, 'Cyton')(
                mode,
                endpoint,
                host=None,
                daisy=daisy,
                montage=pickle.dumps(montage),
                streaming_package_size=streaming_package_size,
                capture_stream=capture_stream,
                number_of_channels=number_of_channels,
            )

        else:
            openbci = []
            if montage:
                montage = pickle.loads(montage)
                montage = self.split_montage(montage, number_of_channels)
            else:
                montage = [montage] * len(endpoint)

            for board_id, end, mtg in zip(range(len(endpoint)), endpoint, montage):
                if mode == 'serial':
                    openbci.append(CytonRFDuino(end, host, daisy[board_id], mtg,
                                                streaming_package_size, capture_stream, board_id, len(
                        number_of_channels)))
                elif mode == 'wifi':
                    openbci.append(CytonWiFi(end, host, daisy[board_id], mtg,
                                             streaming_package_size, capture_stream, board_id, len(
                        number_of_channels)))

            self.openbci = openbci

    # ----------------------------------------------------------------------
    def __getattribute__(self, attr: str) -> Any:
        """Some attributes must be acceded from RPyC."""

        if super().__getattribute__('remote_host'):
            return getattr(super().__getattribute__('remote_host'), attr)
        # return super().__getattribute__(attr)

        openbci = super().__getattribute__('openbci')
        if isinstance(openbci, list):

            if isinstance(getattr(openbci[0], attr), (types.MethodType, types.FunctionType)):
                # The mthods will be aplied to all boards
                def wrap(*args, **kwargs):
                    return [getattr(mod, attr)(*args, **kwargs) for mod in openbci]
                return wrap

            # The attribute of the first board will be used by default
            return getattr(openbci[0], attr)

        return super().__getattribute__(attr)

    # ----------------------------------------------------------------------

    def split_montage(self, montage, chs):
        """"""
        split = []
        montage = montage.copy()

        if isinstance(montage, dict):
            montage = list(montage.values())

        for i in chs:
            split.append({(j + 1): montage.pop(0) for j in range(i)})
        return split

    # ----------------------------------------------------------------------
    def split_channels(self, channels):
        """"""
        split = []
        channels = list(channels).copy()
        for i in [16 if mod.daisy else 8 for mod in self.openbci]:
            split.append([i + 1 for i in range(i)])
            # split.append([channels.pop(0) for i in range(i)])
        return split

    # ----------------------------------------------------------------------
    def just_split(self, data):
        """"""
        split = []
        for i in [16 if mod.daisy else 8 for mod in self.openbci]:
            split.append([data.pop(0) for i in range(i)])
        return split

    # ----------------------------------------------------------------------
    def deactivate_channel(self, channels: List[int]) -> None:
        """"""
        for mod, chs in zip(self.openbci, self.split_channels(channels)):
            mod.deactivate_channel(chs)

    # ----------------------------------------------------------------------
    def activate_channel(self, channels: List[int]) -> None:
        """"""
        for mod, chs in zip(self.openbci, self.split_channels(channels)):
            mod.activate_channel(chs)

    # ----------------------------------------------------------------------
    def channel_settings(self, channels, power_down, gain, input_type, bias, srb2, srb1) -> None:
        """"""
        if isinstance(srb2, (bytes, str)):
            srb2 = [srb2] * len(channels)

        for mod, chs, srb2_ in zip(self.openbci, self.split_channels(channels), self.just_split(srb2)):
            mod.channel_settings(chs, power_down, gain,
                                 input_type, bias, srb2_, srb1)

    # ----------------------------------------------------------------------
    def leadoff_impedance(self, channels, *args, **kwargs) -> None:
        """"""
        for mod, chs in zip(self.openbci, self.split_channels(channels)):
            mod.leadoff_impedance(chs, *args, **kwargs)

    # # ----------------------------------------------------------------------
    # def start_stream(self):
        # """"""
        # for mod in self.openbci:
            # mod.start_stream()

    # # ----------------------------------------------------------------------
    # def stop_stream(self):
        # """"""
        # for mod in self.openbci:
            # mod.stop_stream()
