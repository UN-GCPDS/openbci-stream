import tables
import numpy as np
import json
import logging

from functools import cached_property
from scipy.interpolate import interp1d


########################################################################
class HDF5_Writer:
    """"""

    # ----------------------------------------------------------------------
    def __init__(self, filename):
        """Constructor"""
        self.filename = filename
        self.__open()

    # ----------------------------------------------------------------------
    def close(self):
        """"""
        self.f.close()

    # ----------------------------------------------------------------------
    def add_timestamp(self, timestamp):
        """"""
        self.array_dtm.append(timestamp)

    # ----------------------------------------------------------------------
    def add_header(self, header):
        """"""
        self.array_hdr.append([json.dumps(header)])

    # ----------------------------------------------------------------------
    def add_marker(self, marker, timestamp):
        """"""
        # self.array_mkr.append(
            # [json.dumps({'marker': marker, 'timestamp': timestamp, })])
        self.array_mkr.append([json.dumps([timestamp, marker])])

    # ----------------------------------------------------------------------
    def add_eeg(self, eeg_data, timestamp=None):
        """The fist data conditionate the number of channels.

        """
        if self.array_eeg is None:
            _, channels = eeg_data.shape
            atom_eeg = tables.Float64Atom()
            self.array_eeg = self.f.create_earray(
                self.f.root, 'eeg_data', atom_eeg, shape = (0, channels), title='EEG time series')

        self.array_eeg.append(eeg_data)

        if isinstance(timestamp, (np.ndarray, list, tuple)):

            assert len(timestamp) == len(eeg_data), "Is not recommended add data and timestamp from different sizes."
            self.add_timestamp(timestamp)

        elif timestamp != None:
            timestamp_ = np.zeros(len(eeg_data))
            timestamp_[-1] = timestamp
            self.add_timestamp(timestamp_)

    # ----------------------------------------------------------------------
    def __enter__(self):
        """"""
        return self

    # ----------------------------------------------------------------------
    def __open(self):
        """"""
        self.f = tables.open_file(self.filename, mode = 'w')

        # atom_eeg = tables.Float64Atom()
        atom_dtm = tables.Float64Atom()
        atom_json = tables.StringAtom(itemsize = 2**15)

        self.array_hdr = self.f.create_earray(
            self.f.root, 'header', atom_json, shape=(0,), title='HEADER')
        # self.array_eeg = f.create_earray(
            # f.root, 'eeg_data', atom_eeg, shape=(0, CHANNELS), title='EEG time series')
        self.array_eeg = None
        self.array_dtm = self.f.create_earray(
            self.f.root, 'timestamp', atom_dtm, shape=(0,), title='EEG timestamp')
        self.array_mkr = self.f.create_earray(
            self.f.root, 'markers', atom_json, shape=(0,), title='EEG markers')

    # ----------------------------------------------------------------------
    def __exit__(self, exc_type, exc_val, exc_tb):
        """"""
        self.f.close()

        if exc_type:
            logging.warning(exc_type)
        if exc_val:
            logging.warning(exc_val)
        if exc_tb:
            logging.warning(exc_tb)

    # ----------------------------------------------------------------------
    def close(self):
        """"""
        self.f.close()


########################################################################
class HDF5_Reader:
    """"""

    # ----------------------------------------------------------------------
    def __init__(self, filename):
        """Constructor"""
        self.filename = filename
        self.__open()

    # ----------------------------------------------------------------------
    @cached_property
    def header(self):
        """"""
        return json.loads(self.f.root.header[0])

    # ----------------------------------------------------------------------
    @property
    def eeg(self):
        """"""
        return self.f.root.eeg_data

    # ----------------------------------------------------------------------
    @property
    def markers(self):
        """"""
        markers = {}
        for mkr in self.f.root.markers:
            t, marker = json.loads(mkr)
            markers.setdefault(marker, []).append(t)

        return markers

    # ----------------------------------------------------------------------
    @property
    def timestamp(self):
        """"""
        timestamp = self.f.root.timestamp
        nonzero = np.nonzero(timestamp)
        args = np.arange(self.eeg.shape[0])

        interp = interp1d(
            args[nonzero], timestamp[nonzero], fill_value="extrapolate")
        timestamp = interp(args)
        return timestamp

    # ----------------------------------------------------------------------
    def __enter__(self):
        """"""
        return self

    # ----------------------------------------------------------------------
    def __open(self):
        """"""
        self.f = tables.open_file(self.filename, mode='r')
        # return self

    # ----------------------------------------------------------------------
    def __exit__(self, exc_type, exc_val, exc_tb):
        """"""
        self.f.close()

        if exc_type:
            logging.warning(exc_type)
        if exc_val:
            logging.warning(exc_val)
        if exc_tb:
            logging.warning(exc_tb)

    # ----------------------------------------------------------------------
    def close(self):
        """"""
        self.f.close()
