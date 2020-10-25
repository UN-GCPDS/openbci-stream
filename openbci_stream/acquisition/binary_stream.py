"""
=============
Binary stream
=============

"""

from kafka import KafkaProducer
import pickle
import logging


########################################################################
class BinaryStream:
    """"""
    TOPIC = 'binary'
    cum = b''

    # ----------------------------------------------------------------------
    def __init__(self, streaming_package_size):
        """"""
        logging.info(f'Creating {self.TOPIC} Produser')
        self.streaming_package_size = streaming_package_size
        self.producer = KafkaProducer(bootstrap_servers=['localhost:9092'],
                                      compression_type='gzip',
                                      value_serializer=pickle.dumps,
                                      # request_timeout_ms=30000,
                                      # heartbeat_interval_ms=10000,
                                      )

    # ----------------------------------------------------------------------
    def stream(self, data):
        """"""
        self.cum += data['data']

        if data['context']['connection'] == 'serial':
            f = 1

        elif data['context']['connection'] == 'wifi' and not data['context']['daisy']:
            f = 1

        elif data['context']['connection'] == 'wifi' and data['context']['daisy']:
            f = 2

        if len(self.cum) > (self.streaming_package_size * 33 * f):

            data['data'] = self.cum
            self.producer.send(self.TOPIC, data)
            self.cum = b''

    # ----------------------------------------------------------------------
    def close(self):
        """"""
        logging.info(f'Clossing {self.TOPIC} Produser')
        self.producer.close(timeout=0.3)


