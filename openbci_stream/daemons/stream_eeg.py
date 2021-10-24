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
# import struct
# from functools import cached_property
import numpy as np
# from multiprocessing import Pool
# from datetime import datetime
# import rawutil
import logging

from kafka import KafkaConsumer, KafkaProducer
from typing import TypeVar  # , List, Dict, Tuple, Any


from queue import LifoQueue as queue


from openbci_stream.utils import autokill_process
autokill_process(name=f'binary_2_eeg_base')

DEBUG = ('--debug' in sys.argv)

if DEBUG:
    logging.getLogger().setLevel(logging.DEBUG)
    # logging.getLogger('kafka').setLevel(logging.WARNING)

KafkaStream = TypeVar('kafka-stream')


########################################################################
class EEG:
    """Kafka transformer with parallel implementation for processing binary raw
    data into EEG microvolts. This script requires the Kafka daemon running and
    enables an `auto-kill process <openbci_stream.utils.pid_admin.rst#module-openbci_stream.utils.pid_admin>`_
    """

    # ----------------------------------------------------------------------
    def __init__(self):
        """"""
        self.consumer_eegn = KafkaConsumer(bootstrap_servers=['localhost:9092'],
                                           value_deserializer=pickle.loads,
                                           auto_offset_reset='latest',
                                           )
        self.consumer_eegn.subscribe(['eeg0', 'eeg1', 'eeg2', 'eeg3'])

        self.producer_eeg = KafkaProducer(bootstrap_servers=['localhost:9092'],
                                          compression_type='gzip',
                                          value_serializer=pickle.dumps,
                                          batch_size=2 ** 16,
                                          )

    # ----------------------------------------------------------------------
    def consume(self) -> None:
        """Infinite loop for read Kafka stream."""
        eeg_historical = {'eeg0': queue(),
                          'eeg1': queue(),
                          'eeg2': queue(),
                          'eeg3': queue(),
                          }
        while True:
            for record in self.consumer_eegn:
                logging.info(
                    f"processing {record.topic}:{len(record.value['data'])}")
                eeg_historical[record.topic].put(record)

                count = record.value['context']['parallel_boards']
                data = [eeg_historical[f'eeg{c}'].qsize()
                        for c in range(count)]

                while min(data) > 0:

                    if all(data):
                        logging.debug(f'Preparing stream {data}')
                        stream = [
                            eeg_historical[f'eeg{c}'].get() for c in range(count)]
                        eeg_data = [s.value['data'] for s in stream]
                        context = stream[0].value['context']

                        # montage
                        logging.debug('Creating montage')
                        montage = [s.value['context']['montage']
                                   for s in stream]
                        montage_ = []
                        for items, i in zip([list(m.items()) for m in montage], [0] + [len(m) for m in montage][:-1]):
                            items, i
                            montage_.extend([(m[0] + i, m[1])
                                             for m in items])
                        montage = dict(montage_)

                        #  context
                        logging.debug('Creating context')
                        context['montage'] = montage
                        context['timestamp.binary'] = [
                            s.value['context']['timestamp.binary'] for s in stream]
                        context['daisy'] = [s.value['context']['daisy']
                                            for s in stream]
                        context['timestamp.eeg'] = [
                            s.value['context']['timestamp.eeg'] for s in stream]
                        context['timestamp.binary.consume'] = [
                            s.value['context']['timestamp.binary.consume'] for s in stream]
                        context['buffer'] = data

                        logging.debug('Preparing EEG data')
                        cuteeg = min([d[0].shape[1] for d in eeg_data])
                        eeg = np.concatenate([d[0][:, :cuteeg]
                                              for d in eeg_data], axis=0)
                        if cuteeg:
                            logging.debug(f'>Loaded {cuteeg} samples')

                        if eeg_data[0][1].size:
                            logging.debug(f'Preparing AUX data')
                            cutaux = min([d[1].shape[1] for d in eeg_data])
                            aux = np.concatenate(
                                [d[1][:, :cutaux] for d in eeg_data], axis=0)
                            if cutaux:
                                logging.debug(f'Loaded {cutaux} samples')
                        else:
                            logging.debug(f'No Auxiliar data')
                            aux = None

                        # EEG
                        logging.debug(f'Streaming EEG({eeg.shape})')
                        context['samples'] = eeg.shape[1]
                        self.producer_eeg.send(
                            'eeg', {'context': context.copy(), 'data': eeg.copy()})
                        # fut_eeg = self.producer_eeg.send(
                            # 'eeg', {'context': context.copy(), 'data': eeg.copy()})
                        # try:
                            # fut_eeg.get()
                        # except Exception as e:
                            # logging.error(e)

                        # Aux
                        if aux.size:
                            logging.debug(f'Streaming AUX({aux.shape})')
                            context['samples'] = aux.shape[1]
                            self.producer_eeg.send(
                                'aux', {'context': context.copy(), 'data': aux.copy()})
                            # fut_aux = self.producer_eeg.send(
                                # 'aux', {'context': context.copy(), 'data': aux.copy()})
                            # try:
                                # fut_aux.get()
                            # except Exception as e:
                                # logging.error(e)

                    else:
                        logging.debug(f'Not enought data {data}')

                    data = [eeg_historical[f'eeg{c}'].qsize()
                            for c in range(count)]


if __name__ == '__main__':
    tranformer = EEG()
    tranformer.consume()
