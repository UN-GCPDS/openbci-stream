"""
=============
Binary stream
=============

This module must be run in the same machine that OpenBCI hardware was attached.
"""

import pickle
import logging
from datetime import datetime
from typing import Dict, Any

from kafka import KafkaProducer


########################################################################
class BinaryStream:
    """Kafka producer for equal size packages streaming.

    The dictionary streamed contain two objects: `data` and `context`.

    **data:** Bytes with binary raw data.

    **context:** A dictionary with the following keys:

    * **created:**  The `timestamp` for the exact moment when binary data was read.
    * **daisy:** `True` if Daisy board is attached, otherwise `False`.
    * **boardmode:** Can be `default`, `digital`, ''analog', 'debug' or `marker`.
    * **montage:** A list means consecutive channels e.g. `['Fp1', 'Fp2', 'F3', 'Fz', 'F4']` and a dictionary means specific channels  `{1: 'Fp1', 2: 'Fp2', 3: 'F3', 4: 'Fz', 5: 'F4'}`.
    * **connection:** Can be `serial` or `wifi`.
    * **gain:** Array with gains.

    e.g

    >>> context = {'created': 1604196938.727064,
                   'daisy': False,
                   'boardmode': 'default',
                   'montage': ['Fp1', 'Fp2', 'F3', 'Fz', 'F4'],
                   'connection': 'wifi',
                   'gain': [24, 24, 24, 24, 24, 24, 24, 24]
                   }
    """

    accumulated = b''

    # ----------------------------------------------------------------------
    def __init__(self, streaming_package_size: int, board_id: str = '') -> None:
        """
        Parameters
        ----------
        streaming_package_size
            The package size for streaming packages.
        """

        self.topic = f'binary{board_id}'

        logging.info(f'Creating {self.topic} Produser')
        self.streaming_package_size = streaming_package_size
        self.producer = KafkaProducer(bootstrap_servers=['localhost:9092'],
                                      compression_type='gzip',
                                      value_serializer=pickle.dumps,
                                      )

    # ----------------------------------------------------------------------
    def stream(self, data: Dict[str, Any]) -> None:
        """This stream attempts to create packages of the same size.

        Over WiFi and Daisy, the sampling frequency is doubled in favor to get
        all 16 channels, so the size of the packages is also doubled.

        Parameters
        ----------
        data
            Dictionary with context and raw binary data.
        """
        self.accumulated += data['data']

        if data['context']['connection'] == 'wifi' and data['context']['daisy']:
            f = 2
        else:
            f = 1
        size = self.streaming_package_size * 33 * f

        if len(self.accumulated) >= size:
            data['data'] = self.accumulated[:size]
            data['context']['timestamp.binary'] = datetime.now().timestamp()
            self.producer.send(self.topic, data)
            self.accumulated = self.accumulated[size:]

    # ----------------------------------------------------------------------
    def close(self) -> None:
        """Terminate the produser."""
        logging.info(f'Clossing {self.topic} Produser')
        self.producer.close(timeout=0.3)
