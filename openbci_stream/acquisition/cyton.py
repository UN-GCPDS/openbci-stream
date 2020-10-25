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
import pickle
import socket
import logging
import asyncore
from threading import Thread
from datetime import datetime

import requests
import serial

from .cyton_base import CytonBase
from .tcp_server import WiFiShieldTCPServer

import rpyc

DEFAULT_LOCAL_IP = "192.168.1.1"


########################################################################
class CytonRFDuino(CytonBase):
    """
    RFduino is the default communication mode for Cyton 32 bit, this set a
    serial comunication through a USB dongle with a sample frequency of `250`
    Hz, for 8 or 16 channels.
    """

    # ----------------------------------------------------------------------
    def __init__(self, port=None, host=None, daisy='auto', capture_stream=False, montage=None, streaming_package_size=250):
        """RFduino mode connection.

        Parameters
        ----------
        port : str, optional
            Specific serial port for connection.
        montage: dic, list, optional
            Decription of channels used.
        timeout: float, optional.
            Read timeout for serial connection.
        write_timeout: float, optional.
            Write timeout for serial connection.
        """

        self.remote_host = None

        self._markers = None

        if host == 'localhost':
            host = None

        if host:
            rpyc_service = rpyc.connect(host, 18861)
            self.remote_host = getattr(rpyc_service.root, self.__class__.__name__)(
                port, False, False, pickle.dumps(montage), streaming_package_size)
            return

        if port is None:
            port = self._get_serial_ports()
            if port:
                logging.info(f"Port {port} found.")

        if port is None:
            logging.error("No device was auto detected.")
            sys.exit()

        # try:
        self.device = serial.Serial(port, 115200, timeout=0.1,
                                    write_timeout=0.01,
                                    parity=serial.PARITY_NONE,
                                    stopbits=serial.STOPBITS_ONE)
        super().__init__(daisy, capture_stream, montage, streaming_package_size)

        # self.stop_stream()

        # Getter call
        # self.boardmode

        # self.command(self.SOFT_RESET)  # to update the status information

        # except Exception as e:
            # logging.error(f"Impossible to connect with {port}.")
            # logging.error(e)
            # sys.exit()

    # ----------------------------------------------------------------------
    def __str__(self):
        """"""
        return "CytonRFDuino"

    # ----------------------------------------------------------------------
    def __getattribute__(self, attr):
        """"""
        if super().__getattribute__('remote_host'):

            if attr == 'capture_stream':
                logging.warning(
                    "Romete mode not support stream capture, `openbci.consumer.OpenBCIConsumer` must be used.")
                return lambda: None
            return getattr(super().__getattribute__('remote_host'), attr)
        else:
            return super().__getattribute__(attr)

    # ----------------------------------------------------------------------
    def _get_serial_ports(self):
        """Look for first available port with OpenBCI device.

        Returns
        -------
        str
            String with the port name or None if no ports were founded.
        """

        if os.name == 'nt':
            prefix = 'COM{}',
        elif os.name == 'posix':
            prefix = '/dev/ttyACM{}', '/dev/ttyUSB{}',

        for pref in prefix:
            for i in range(20):
                port = pref.format(i)
                try:
                    d = serial.Serial(port, timeout=0.2)
                    if d.write(self.START_STREAM):
                        d.close()
                        return port
                except:
                    continue

    # ----------------------------------------------------------------------
    def read(self, size):
        """Read size bytes from the serial port.

        Parameters
        ----------
        size : int
            Size of input buffer.

        Returns
        -------
        bytes
            Data readed.
        """
        try:
            return self.device.read(size)
        except:
            return self.read(size)

    # ----------------------------------------------------------------------
    def write(self, data):
        """Output the given data over the serial port."""

        return self.device.write(data)

    # ----------------------------------------------------------------------
    def reset_input_buffer(self):
        """Clear input buffer, discarding all that is in the buffer."""
        self.device.reset_input_buffer()

    # ----------------------------------------------------------------------
    def close(self):
        """Close the serial communication."""

        self.device.close()

    # ----------------------------------------------------------------------
    def _stream_data(self, size=2**8, kafka_context={}):
        """Load binary data and put in a queue.

        For optimizations issues the data must be read in packages but write one
        to one in a queue, this method must be executed on a thread.

        Parameters
        ----------
        size : int, optional
            The buffer length for read.
        kafka_context : dict

        """

        # while self.READING:
        while binary := self.read(size):
            try:
                kafka_context.update({'created': datetime.now().timestamp()})
                data = {'context': kafka_context,
                        'data': binary,
                        }
                self.binary_stream.stream(data)
            except serial.SerialException as e:
                logging.error(e)

    # ----------------------------------------------------------------------
    def start_stream(self, clear=True, wait_for_data=False):
        """"""
        kafka_context = {'daisy': self.daisy,
                         'boardmode': self.boardmode,
                         'montage': self.montage,
                         'connection': 'serial',
                         # 'created': datetime.now().timestamp(),
                         }

        self.command(self.START_STREAM)
        super().start_stream(clear)

        # Thread for read data
        if hasattr(self, "thread_data_collect") and self.thread_data_collect.isAlive():
            pass
        else:
            self.thread_data_collect = Thread(
                target=self._stream_data, args=(2**8, kafka_context))
            self.thread_data_collect.start()

        if wait_for_data:
            self._wait_for_data()

    # ----------------------------------------------------------------------
    def stop_stream(self, wait_for_no_data=False):
        """Stop a data collection that run asynchronously."""

        self.command(self.STOP_STREAM)
        super().stop_stream()

        self.binary_stream.close()

        if wait_for_no_data:
            self._wait_for_no_data()

    # ----------------------------------------------------------------------

    def reset_input_buffer(self):
        """Device handled process, flush input data."""
        self.device.reset_input_buffer()
        self.device.flushInput()


########################################################################
class CytonWiFi(CytonBase):
    """
    This module implement a TCP connection using the WiFi module, this module
    was designed for works with se same syntax that `CytonRFDuino`.
    """

    # ----------------------------------------------------------------------
    def __init__(self, ip_address, host=None, daisy='auto', capture_stream=False, montage=None, streaming_package_size=1e3):
        """WiFi mode connection.

        Parameters
        ----------
        ip_address: str.
            IP address with for WiFi module.
        montage: dictl, list, optional
            Decription of channels used.
        """

        self.remote_host = None

        self._ip_address = ip_address
        self._readed = None
        self._local_ip_address = self._get_local_ip_address()

        if host == 'localhost':
            host = None

        if host:
            try:
                rpyc_service = rpyc.connect(host, 18861)
                self.remote_host = getattr(rpyc_service.root, self.__class__.__name__)(
                    self._ip_address,
                    host=None,
                    daisy=daisy,
                    capture_stream=False,
                    montage=pickle.dumps(montage),
                    streaming_package_size=streaming_package_size)
            except socket.gaierror:
                logging.error("'openbci_rpyc' daemon are running?")

            return

        super().__init__(daisy, capture_stream, montage, streaming_package_size)

        self._create_tcp_server()
        time.sleep(5)

        self._start_loop()
        # self._start_tcp_client()

    # ----------------------------------------------------------------------

    def __str__(self):
        """"""
        return "CytonWiFi"

    # ----------------------------------------------------------------------
    def __getattribute__(self, attr):
        """"""
        if super().__getattribute__('remote_host'):

            if attr == 'capture_stream':
                logging.warning(
                    "Romete mode not support stream capture, `openbci.consumer.OpenBCIConsumer` must be used.")
                return lambda: None
            return getattr(super().__getattribute__('remote_host'), attr)
        else:
            return super().__getattribute__(attr)

    # ----------------------------------------------------------------------
    def _get_local_ip_address(self):
        """Get the current network IP assigned."""

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip_address = s.getsockname()[0]
            s.close()
            return local_ip_address

        except:
            logging.warning('Impossible to detect a network connection, it must '
                            'be connected to some network if you are trying to '
                            'use a WiFi module.')
            sys.exit()

    # ----------------------------------------------------------------------
    def write(self, data):
        """Send command to board through HTTP protocole."""

        if hasattr(data, 'decode'):
            data = data.decode()
        elif isinstance(data, int):
            data = chr(data)

        try:
            logging.info(f"Sending command: '{data}'")
            response = requests.post(
                f"http://{self._ip_address}/command", json={'command': data})
        except Exception as e:
            logging.info(f"Error on sending command '{data}': {e}")
            return

        if response.status_code == 200:
            self._readed = response.text
        elif response.status_code == 502:
            logging.info(f"No confirmation from board, does not mean fail.")
        else:
            logging.warning(
                f"Error code: {response.status_code} {response.text}")
            self._readed = None

    # ----------------------------------------------------------------------

    def read(self, size=None):
        """Read the response for some command.

        Not all command return response.
        """

        time.sleep(0.2)  # very important dealy for wait a response.
        return self._readed

    # ----------------------------------------------------------------------
    def start_stream(self, clear=True, wait_for_data=False):
        """Start a data collection asynchronously.

        Send a command to the board for start the streaming through TCP.

        Parameters
        ----------
        milliseconds: int, optional
            The duration of data for packing.
        """

        super().start_stream(clear)
        self._start_tcp_client()

        # if not self.STREAMING:
        response = requests.get(f"http://{self._ip_address}/stream/start")
        if response.status_code != 200:
            logging.warning(
                f"Unable to start streaming.\nCheck API for status code {response.status_code} on /stream/start")
            # self.STREAMING = True
        else:

            if wait_for_data:
                self._wait_for_data()

    # ----------------------------------------------------------------------
    def stop_stream(self, wait_for_no_data=False):
        """Stop streaming."""

        super().stop_stream()

        # if self.STREAMING:
            # self.stop_loop()
        response = requests.get(f"http://{self._ip_address}/stream/stop")
        if response.status_code != 200:
            # self.STREAMING = False
        # else:
            logging.warning(
                f"Unable to stop streaming.\nCheck API for status code {response.status_code} on /stream/start")

        self.binary_stream.close()
        # self._stop_tcp_client()
        asyncore.close_all()

        if wait_for_no_data:
            self._wait_for_no_data()

    # ----------------------------------------------------------------------
    def _create_tcp_server(self):
        """Create TCP server.

        This server will handle the streaming EEG data.
        """

        kafka_context = {
            'daisy': self.daisy,
            'boardmode': self.boardmode,
            'montage': self.montage,
            'connection': 'wifi',
        }

        self.local_wifi_server = WiFiShieldTCPServer(self._local_ip_address,
                                                     lambda: getattr(
                                                         self, 'binary_stream'),
                                                     kafka_context,
                                                     )
        self.local_wifi_server_port = self.local_wifi_server.socket.getsockname()[
            1]
        logging.info(
            f"Opened socket on {self._local_ip_address}:{self.local_wifi_server_port}")

    # ----------------------------------------------------------------------
    def _start_tcp_client(self):
        """Connect the board to the TCP server.

        Send configuration of the previous server created to the board, so they
        can connected to.
        """

        if self._ip_address is None:
            raise ValueError('self._ip_address cannot be None')

        logging.info(f"Init WiFi connection with IP: {self._ip_address}")

        self.requests_session = requests.Session()

        # requests.get(f"http://{self._ip_address}/yt")
        response = requests.get(f"http://{self._ip_address}/board")

        if response.status_code == 200:
            board_info = response.json()

            if not board_info['board_connected']:
                raise RuntimeError("No board connected to WiFi Shield.")
            self._gain = board_info['gains']

        res_tcp_post = requests.post(f"http://{self._ip_address}/tcp",
                                     json={
                                        'ip': self._local_ip_address,
                                        'port': self.local_wifi_server_port,
                                        'output': 'json',
                                        'delimiter': True,
                                        'latency': 10,
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
    def close(self):
        """Stop TCP server."""
        self.stop_stream()
        requests.delete(f"http://{self._ip_address}/tcp")
        # asyncore.close_all()

    # ----------------------------------------------------------------------
    def _start_loop(self):
        """Start the TCP server. """
        self.th_loop = Thread(target=asyncore.loop, args=(), )
        self.th_loop.start()


########################################################################
class Cyton:
    """
    Main
    """

    # ----------------------------------------------------------------------
    def __new__(self, mode, endpoint=None, host=None, daisy='auto', capture_stream=False, montage=None, streaming_package_size=None):
        """Constructor"""
        if host and capture_stream:
            logging.warning(
                '`capture_stream` and `host` arguments are not available together yet.')

        if mode == 'serial':
            if streaming_package_size is None:
                streaming_package_size = 250
            mode = CytonRFDuino(endpoint, host, daisy,
                                capture_stream, montage, streaming_package_size)

        elif mode == 'wifi':
            if streaming_package_size is None:
                streaming_package_size = 1e3
            mode = CytonWiFi(endpoint, host, daisy,
                             capture_stream, montage, streaming_package_size)

        return mode
