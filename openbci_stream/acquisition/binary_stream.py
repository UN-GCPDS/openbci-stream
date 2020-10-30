"""
=============
Binary stream
=============

This module must be run in the same machine that OpenBCI hardware was attached.
"""

from kafka import KafkaProducer
import pickle
import logging

from typing import Dict, Any


########################################################################
class BinaryStream:
    """Kafka producer for equal size packages streaming."""

    TOPIC = 'binary'
    accumulated = b''

    # ----------------------------------------------------------------------
    def __init__(self, streaming_package_size: int) -> None:
        """
        Parameters
        ----------
        streaming_package_size
            The package size for streaming packages.
        """

        logging.info(f'Creating {self.TOPIC} Produser')
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

        if data['context']['connection'] == 'wifi' and data['context']['daisy']:
            f = 2
        else:
            f = 1

        if len(self.accumulated) > (self.streaming_package_size * 33 * f):
            data['data'] = self.accumulated
            self.producer.send(self.TOPIC, data)
            self.accumulated = b''

    # ----------------------------------------------------------------------
    def close(self) -> None:
        """Terminate the produser."""
        logging.info(f'Clossing {self.TOPIC} Produser')
        self.producer.close(timeout=0.3)


