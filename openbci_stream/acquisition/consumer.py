"""
================
OpenBCI Consumer
================

"""

import pickle
import logging

from .cyton import Cyton

from kafka import KafkaConsumer


########################################################################
class OpenBCIConsumer:
    """"""

    # ----------------------------------------------------------------------
    def __init__(self, mode=None, endpoint=None, host='localhost', daisy='auto', montage=None, streaming_package_size=None):
        """"""
        self.bootstrap_servers = [f'{host}:9092']
        self.topics = ['eeg', 'marker']

        if mode:
            self.openbci = Cyton(mode, endpoint, host,
                                 daisy, False, montage, streaming_package_size)

    # ----------------------------------------------------------------------
    def deserialize(self, data):
        """"""
        try:
            return pickle.loads(data)
        except:
            return data

    # ----------------------------------------------------------------------
    def __enter__(self):
        """"""
        if hasattr(self, 'openbci'):
            self.openbci.start_stream()
        self.consumer = KafkaConsumer(bootstrap_servers=self.bootstrap_servers,
                                      value_deserializer=self.deserialize,
                                      # group_id='openbci',
                                      auto_offset_reset='latest',
                                      )
        self.consumer.subscribe(self.topics)
        # return self.consumer
        if hasattr(self, 'openbci'):
            return self.consumer, self.openbci
        else:
            return self.consumer

    # ----------------------------------------------------------------------
    def __exit__(self, exc_type, exc_val, exc_tb):
        """"""
        if hasattr(self, 'openbci'):
            self.openbci.stop_stream()
        self.consumer.close()

        if exc_type:
            logging.warning(exc_type)
        if exc_val:
            logging.warning(exc_val)
        if exc_tb:
            logging.warning(exc_tb)


if __name__ == '__main__':

    with OpenBCIConsumer(start=True, endpoint='serial') as stream:
        for message in stream:

            print(message.topic)

            message.topic,
            message.partition,
            message.offset,
            message.key,
            message.value,
            message.timestamp
