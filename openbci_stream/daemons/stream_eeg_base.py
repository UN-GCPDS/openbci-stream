"""
=============
Binary to EEG
=============

A transformer for Kafka that reads binary data and stream EEG data.

Binary -> Kafka-Transformer -> EEG

For examples and descriptions refers to documentation:
`Data storage handler <../A1-raw_cleaning.ipynb>`_
"""

import sys
import pickle
import struct
from functools import cached_property
import numpy as np
from multiprocessing import Pool
from datetime import datetime
import rawutil
import logging

from kafka import KafkaConsumer, KafkaProducer
from typing import TypeVar, List, Dict, Tuple, Any


from queue import Queue


from openbci_stream.utils import autokill_process
autokill_process(name=f'binary_2_eeg{sys.argv[1]}')

DEBUG = ('--debug' in sys.argv)
KafkaStream = TypeVar('kafka-stream')


########################################################################
class BinaryToEEG:
    """Kafka transformer with parallel implementation for processing binary raw
    data into EEG microvolts. This script requires the Kafka daemon running and
    enables an `auto-kill process <openbci_stream.utils.pid_admin.rst#module-openbci_stream.utils.pid_admin>`_
    """

    # ----------------------------------------------------------------------
    def __init__(self):
        """"""
        self.board_id = board_id

        self.consumer_eegn = KafkaConsumer(bootstrap_servers=['localhost:9092'],
                                           value_deserializer=pickle.loads,
                                           auto_offset_reset='latest',
                                           )
        self.consumer_eegn.subscribe(['eeg0', 'eeg1', 'eeg2', 'eeg3'])

        self.producer_eeg = KafkaProducer(bootstrap_servers=['localhost:9092'],
                                          compression_type='gzip',
                                          value_serializer=pickle.dumps,
                                          )

    # ----------------------------------------------------------------------
    def consume(self) -> None:
        """Infinite loop for read Kafka stream."""

        eeg0 = Queue(5)
        eeg1 = Queue(5)
        eeg2 = Queue(5)
        eeg3 = Queue(5)

        while True:
            for record in self.consumer_eegn:
                if DEBUG:
                    logging.info(f"processing {len(record.value['data'])}")

                if record.topic == 'eeg0':
                    eeg0.put(record.data.value['data'])
                elif record.topic == 'eeg1':
                    eeg1.put(record.data.value['data'])
                elif record.topic == 'eeg2':
                    eeg2.put(record.data.value['data'])
                elif record.topic == 'eeg3':
                    eeg3.put(record.data.value['data'])

                if all[eeg0.qsize(), eeg1.qsize(), eeg2.qsize(), eeg3.qsize()]:


if __name__ == '__main__':
    tranformer = BinaryToEEG()
    tranformer.consume()
