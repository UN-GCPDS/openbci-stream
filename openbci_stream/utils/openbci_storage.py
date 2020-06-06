"""
===============
OpenBCI-Storage
===============

A consumer for Kafka that write the EEG data into an HDF5 file.

       +------------+
       |            |
EEG -> |  Consumer  | -> HDF5
       |            |
       +------------+


"""

import tables
import numpy as np
import json
from kafka import KafkaConsumer
import pickle


########################################################################
class EEGDataStructure:
    """"""

    # ----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""

        atom_eeg = tables.Float64Atom()
        atom_dtm = tables.Float64Atom()
        atom_json = tables.StringAtom(itemsize=2**15)

        self.array_hdr = f.create_earray(
            f.root, 'header', atom_json, shape=(0,), title='HEADER')
        self.array_eeg = f.create_earray(
            f.root, 'eeg_data', atom_eeg, shape=(0, CHANNELS), title='EEG time series')
        self.array_dtm = f.create_earray(
            f.root, 'datetime', atom_dtm, shape=(0,), title='EEG datetime')
        self.array_mkr = f.create_earray(
            f.root, 'marker', atom_json, shape=(0,), title='EEG markers')

    # ----------------------------------------------------------------------
    def add_header(self, data):
        """"""
        self.array_hdr.append([json.dumps(data)])

    # ----------------------------------------------------------------------
    def add_marker(self, datetime, marker):
        """"""
        self.array_mkr.append([json.dumps(marker)])

    # ----------------------------------------------------------------------
    def __enter__(self):
        """"""

    # ----------------------------------------------------------------------
    def __exit__(self, exc_type, exc_val, exc_tb):
        """"""
        # if hasattr(self, 'openbci'):
            # self.openbci.stop_stream()
        # self.consumer.close()

        if exc_type:
            logging.warning(exc_type)
        if exc_val:
            logging.warning(exc_val)
        if exc_tb:
            logging.warning(exc_tb)


########################################################################
class Storage:
    """"""

    # ----------------------------------------------------------------------
    def __init__(self, host='localhost'):
        """Constructor"""

        self.bootstrap_servers = [f'{host}:9092']
        self.topics = ['eeg', 'marker']

        self.consumer = KafkaConsumer(bootstrap_servers=self.bootstrap_servers,
                                      value_deserializer=self.deserialize,
                                      # group_id='openbci',
                                      auto_offset_reset='latest',
                                      )

    # ----------------------------------------------------------------------
    def deserialize(self, data):
        """"""
        try:
            return pickle.loads(data)
        except:
            return data

