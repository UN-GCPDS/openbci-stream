"""
====================
Data storage handler
====================


This is a test

"""
import tables
import numpy as np
import json

from functools import cached_property
from scipy.interpolate import interp1d

from typing import Dict, Any, Optional, Text, List, TypeVar
timesamp = TypeVar('timesamp', float, np.float)


########################################################################
class HDF5Writer:
    """"""

    # ----------------------------------------------------------------------
    def __init__(self, filename: str) -> None:
        """Constructor"""
        if filename.endswith('h5'):
            self.filename = f'{filename}'
        else:
            self.filename = f'{filename}.h5'

        self._open()

    # ----------------------------------------------------------------------
    def close(self) -> None:
        """"""
        self.f.close()

    # ----------------------------------------------------------------------
    def add_timestamp(self, timestamp: timesamp) -> None:
        """"""
        self.array_dtm.append(timestamp)

    # ----------------------------------------------------------------------
    def add_header(self, header: Dict[str, Any]) -> None:
        """"""
        self.array_hdr.append([json.dumps(header)])

    # ----------------------------------------------------------------------
    def add_marker(self, marker: Any, timestamp: timesamp) -> None:
        """"""
        self.array_mkr.append([json.dumps([timestamp, marker])])

    # ----------------------------------------------------------------------
    def add_annotation(self, onset: int, duration: int = 0, description: str = '') -> None:
        """"""
        self.array_anno.append([json.dumps([onset, duration, description])])

    # ----------------------------------------------------------------------
    def add_eeg(self, eeg_data: np.ndarray, timestamp: Optional[timesamp] = None) -> None:
        """The fist data conditionate the number of channels.
        """
        if self.array_eeg is None:
            channels, _ = eeg_data.shape
            atom_eeg = tables.Float64Atom()
            self.array_eeg = self.f.create_earray(
                self.f.root, 'eeg_data', atom_eeg, shape=(channels, 0), title='EEG time series')

        self.array_eeg.append(eeg_data)

        if isinstance(timestamp, (np.ndarray, list, tuple)):

            assert len(timestamp) == len(
                eeg_data), "Is not recommended add data and timestamp from different sizes."
            self.add_timestamp(timestamp)

        elif timestamp != None:
            timestamp_ = np.zeros(eeg_data.shape[1])
            timestamp_[-1] = timestamp
            self.add_timestamp(timestamp_)

    # ----------------------------------------------------------------------
    def add_aux(self, aux_data: np.ndarray) -> None:
        """"""
        if self.array_aux is None:
            channels, _ = aux_data.shape
            atom_eeg = tables.Float64Atom()
            self.array_aux = self.f.create_earray(
                self.f.root, 'aux_data', atom_eeg, shape=(channels, 0), title='EEG time series')

        self.array_aux.append(aux_data)

        # if isinstance(timestamp, (np.ndarray, list, tuple)):

            # assert len(timestamp) == len(
                # aux_data), "Is not recommended add data and timestamp from different sizes."
            # self.add_timestamp(timestamp)

        # elif timestamp != None:
            # timestamp_ = np.zeros(len(aux_data))
            # timestamp_[-1] = timestamp
            # self.add_timestamp(timestamp_)

    # ----------------------------------------------------------------------
    def __enter__(self) -> None:
        """"""
        return self

    # ----------------------------------------------------------------------
    def _open(self) -> None:
        """"""
        self.f = tables.open_file(self.filename, mode='w')

        # atom_eeg = tables.Float64Atom()
        atom_dtm = tables.Float64Atom()
        atom_json = tables.StringAtom(itemsize=2**15)

        self.array_hdr = self.f.create_earray(
            self.f.root, 'header', atom_json, shape=(0,), title='HEADER')
        # self.array_eeg = f.create_earray(
            # f.root, 'eeg_data', atom_eeg, shape=(0, CHANNELS), title='EEG time series')
        self.array_eeg = None
        self.array_aux = None
        self.array_dtm = self.f.create_earray(
            self.f.root, 'timestamp', atom_dtm, shape=(0,), title='EEG timestamp')
        self.array_mkr = self.f.create_earray(
            self.f.root, 'markers', atom_json, shape=(0,), title='EEG markers')
        self.array_anno = self.f.create_earray(
            self.f.root, 'annotations', atom_json, shape=(0,), title='EEG annotations')

    # ----------------------------------------------------------------------
    def __exit__(self, exc_type: Text, exc_val: Text, exc_tb: Text) -> None:
        """"""
        self.f.close()

        # if exc_type:
            # logging.warning(exc_type)
        # if exc_val:
            # logging.warning(exc_val)
        # if exc_tb:
            # logging.warning(exc_tb)

    # ----------------------------------------------------------------------
    def close(self) -> None:
        """"""
        self.f.close()


########################################################################
class HDF5Reader:
    """"""

    # ----------------------------------------------------------------------
    def __init__(self, filename: str) -> None:
        """Constructor"""
        self.filename = filename
        self._open()

    # ----------------------------------------------------------------------
    @cached_property
    def header(self) -> Dict[str, Any]:
        """"""
        return json.loads(self.f.root.header[0])

    # ----------------------------------------------------------------------
    @property
    def eeg(self) -> np.ndarray:
        """"""
        return self.f.root.eeg_data

    # ----------------------------------------------------------------------
    @property
    def aux(self) -> np.ndarray:
        """"""
        return self.f.root.aux_data

    # ----------------------------------------------------------------------
    @property
    def annotations(self) -> list:
        """"""
        return [json.loads(anno) for anno in self.f.root.annotations]

    # ----------------------------------------------------------------------
    @property
    def markers(self) -> Dict[str, List[timesamp]]:
        """"""
        markers = {}
        for mkr in self.f.root.markers:
            t, marker = json.loads(mkr)
            markers.setdefault(marker, []).append(t)

        return markers

    # ----------------------------------------------------------------------
    @property
    def timestamp(self) -> List[timesamp]:
        """"""
        return self._timestamp(self.eeg.shape[1])

    # ----------------------------------------------------------------------
    @property
    def aux_timestamp(self) -> List[timesamp]:
        """"""
        return self._timestamp(self.aux.shape[1])

    # ----------------------------------------------------------------------
    def _timestamp(self, length: int):
        """"""
        timestamp = self.f.root.timestamp
        nonzero = np.nonzero(timestamp)[0]
        ssr = self.header['streaming_sample_rate']

        x = nonzero * (length / nonzero[-1])
        interp = interp1d(x, timestamp[nonzero], fill_value="extrapolate")

        args = np.arange(-ssr, length - ssr)

        timestamp = interp(args)
        return timestamp

    # ----------------------------------------------------------------------
    def __enter__(self) -> None:
        """"""
        return self

    # ----------------------------------------------------------------------
    def _open(self) -> None:
        """"""
        self.f = tables.open_file(self.filename, mode='r')
        # return self

    # ----------------------------------------------------------------------
    def __exit__(self, exc_type: Text, exc_val: Text, exc_tb: Text) -> None:
        """"""
        self.f.close()

        # if exc_type:
            # logging.warning(exc_type)
        # if exc_val:
            # logging.warning(exc_val)
        # if exc_tb:
            # logging.warning(exc_tb)

    # ----------------------------------------------------------------------
    def close(self) -> None:
        """"""
        self.f.close()
