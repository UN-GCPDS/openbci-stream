"""
================
OpenBCI Consumer
================
"""

import pickle
import logging
from .cyton import Cyton
from typing import Tuple, Optional, Union, Literal

from kafka import KafkaConsumer

# Custom type var
MODE = Literal['serial', 'wifi', None]
DAISY = Literal['auto', True, False]


########################################################################
class OpenBCIConsumer:
    """Kafka consumer for read data streamed.
    This class can start the acquisition if the respective parameter are
    specified. For just connect with an existing stream only needs the **host**,
    argument, the others one are used for start one.

    Connect with an existing stream:

    >>> whith OpenBCIConsumer() as stream:
            for message in stream:
                ...

    Starts serial acquisition, create a stream and it connects with it:

    >>> whith OpenBCIConsumer('serial', '/dev/ttyUSB0') as stream:
            for message in stream:
                ...

    Connect with a remote existing stream:

    >>> whith OpenBCIConsumer(host='192.168.1.113') as stream:
            for message in stream:
                ...

    For examples and descriptions refers to documentation:
    `Controlled execution with OpenBCIConsumer() <../notebooks/03-data_acquisition.html#Controlled-execution-with-OpenBCIConsumer()-class>`_

    Parameters
    ----------
    mode
        If specified, will try to start streaming with this connection mode.
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
    """

    # ----------------------------------------------------------------------
    def __init__(self, mode: MODE = None, endpoint: Optional[str] = None,
                 daisy: DAISY = 'auto',
                 montage: Optional[Union[list, dict]] = None,
                 streaming_package_size: Optional[int] = None,
                 host: Optional[str] = 'localhost') -> None:
        """"""

        self.bootstrap_servers = [f'{host}:9092']
        self.topics = ['eeg', 'marker']

        if mode:
            self.openbci = Cyton(mode, endpoint, host,
                                 daisy, False, montage, streaming_package_size)

    # ----------------------------------------------------------------------
    def __enter__(self) -> Tuple[KafkaConsumer, Optional[Cyton]]:
        """Start stream and create consumer."""

        if hasattr(self, 'openbci'):
            self.openbci.start_stream()
        self.consumer = KafkaConsumer(bootstrap_servers=self.bootstrap_servers,
                                      value_deserializer=pickle.loads,
                                      auto_offset_reset='latest',
                                      )
        self.consumer.subscribe(self.topics)

        if hasattr(self, 'openbci'):
            return self.consumer, self.openbci
        else:
            return self.consumer

    # ----------------------------------------------------------------------
    def __exit__(self, exc_type: str, exc_val: str, exc_tb: str) -> None:
        """Stop stream and close consumer."""

        if hasattr(self, 'openbci'):
            self.openbci.stop_stream()
        self.consumer.close()

        if exc_type:
            logging.warning(exc_type)
        if exc_val:
            logging.warning(exc_val)
        if exc_tb:
            logging.warning(exc_tb)
