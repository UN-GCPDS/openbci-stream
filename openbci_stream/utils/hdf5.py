"""
====================
Data storage handler
====================

"""

import tables
import numpy as np
import json
import logging
import mne
from datetime import datetime

from functools import cached_property
from scipy.interpolate import interp1d

from typing import Dict, Any, Optional, Text, List, TypeVar, Union
timestamp_ = TypeVar('timesamp', float, np.float)


# ----------------------------------------------------------------------
def np2json_serializer(obj):
    """"""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, datetime):
        return obj.__str__()


# ----------------------------------------------------------------------
def interpolate_datetime(timestamp, length, sample_rate):
    """"""
    nonzero = np.nonzero(timestamp)[0]
    x = nonzero * (length / nonzero[-1])
    interp = interp1d(x, timestamp[nonzero], fill_value="extrapolate")
    args = np.arange(-sample_rate, length - sample_rate)

    timestamp = interp(args)
    return timestamp


########################################################################
class HDF5Writer:
    """
    """

    # ----------------------------------------------------------------------
    def __init__(self, filename: str) -> None:
        """Constructor"""
        if filename.endswith('h5'):
            self.filename = f'{filename}'
        else:
            self.filename = f'{filename}.h5'

        self.channels = None
        self._open()

    # ----------------------------------------------------------------------
    def close(self) -> None:
        """"""
        self.f.close()

    # ----------------------------------------------------------------------
    def add_timestamp(self, timestamp: timestamp_) -> None:
        """"""
        self.array_dtm.append(timestamp)

    # ----------------------------------------------------------------------
    def add_header(self, header: Dict[str, Any]) -> None:
        """"""
        self.array_hdr.append([json.dumps(header, default=np2json_serializer)])

    # ----------------------------------------------------------------------
    def add_marker(self, marker: Any, timestamp: timestamp_) -> None:
        """"""
        self.array_mkr.append([json.dumps([timestamp, marker], default=np2json_serializer)])

    # ----------------------------------------------------------------------
    def add_markers(self, markers: Dict[str, List[timestamp_]]) -> None:
        """"""
        for marker in markers:
            for timestamp in markers[marker]:
                self.add_marker(marker, timestamp)

    # ----------------------------------------------------------------------
    def add_annotation(self, onset: int, duration: int = 0, description: str = '') -> None:
        """"""
        self.array_anno.append([json.dumps([onset, duration, description], default=np2json_serializer)])

    # ----------------------------------------------------------------------
    def add_eeg(self, eeg_data: np.ndarray, timestamp: Optional[timestamp_] = None) -> None:
        """The first data conditionate the number of channels.
        """
        if self.array_eeg is None:
            self.channels, _ = eeg_data.shape
            atom_eeg = tables.Float64Atom()
            self.array_eeg = self.f.create_earray(
                self.f.root, 'eeg_data', atom_eeg, shape=(self.channels, 0), title='EEG time series')

        if self.channels != eeg_data.shape[0]:
            logging.warning(f'The number of channels {self.channels} can not be changed!')
            return

        self.array_eeg.append(eeg_data)

        if isinstance(timestamp, (np.ndarray, list, tuple)):

            assert len(timestamp) == eeg_data.shape[1], f"Is not recommended add data and timestamp from different sizes. {len(timestamp)} != {eeg_data.shape[1]}"
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

    # ----------------------------------------------------------------------
    def __enter__(self) -> None:
        """"""
        return self

    # ----------------------------------------------------------------------
    def _open(self) -> None:
        """"""
        self.f = tables.open_file(self.filename, mode='w')

        atom_dtm = tables.Float64Atom()
        atom_json = tables.StringAtom(itemsize=2**15)

        self.array_hdr = self.f.create_earray(
            self.f.root, 'header', atom_json, shape=(0,), title='HEADER')
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
        header = json.loads(self.f.root.header[0])

        if 'channels' in header:
            header['channels'] = {int(k): header['channels'][k] for k in header['channels']}

        return header

    # ----------------------------------------------------------------------
    @cached_property
    def eeg(self) -> np.ndarray:
        """"""
        return np.array(self.f.root.eeg_data).T

    # ----------------------------------------------------------------------
    @cached_property
    def aux(self) -> np.ndarray:
        """"""
        return np.array(self.f.root.aux_data).T

    # ----------------------------------------------------------------------
    @cached_property
    def annotations(self) -> list:
        """"""
        return [json.loads(anno) for anno in self.f.root.annotations]

    # ----------------------------------------------------------------------
    @cached_property
    def markers(self) -> Dict[str, List[timestamp_]]:
        """"""
        markers = {}
        for mkr in self.f.root.markers:
            t, marker = json.loads(mkr)
            markers.setdefault(marker, []).append(t)

        return markers

    # ----------------------------------------------------------------------
    @cached_property
    def markers_relative(self) -> Dict[str, List[int]]:
        """"""
        markers_relative = {}
        for key in self.markers:
            locs = self.markers[key]
            markers_relative[key] = [np.abs(self.timestamp - loc).argmin() for loc in locs]

        return markers_relative

    # ----------------------------------------------------------------------
    @cached_property
    def timestamp(self) -> List[timestamp_]:
        """"""
        return self._timestamp(self.eeg.shape[1])

    # ----------------------------------------------------------------------
    @cached_property
    def aux_timestamp_(self) -> List[timestamp_]:
        """"""
        return self._timestamp(self.aux.shape[1])

    # ----------------------------------------------------------------------
    def _timestamp(self, length: int):
        """"""
        timestamp = self.f.root.timestamp

        if timestamp[timestamp == 0].size > 0:
            ssr = self.header['sample_rate']
            timestamp = interpolate_datetime(timestamp, length, ssr)

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

    # ----------------------------------------------------------------------
    def close(self) -> None:
        """"""
        self.f.close()

    # ----------------------------------------------------------------------
    def get_epochs(self, duration: int, tmin: Optional[int] = 0, markers: Union[None, List[str]] = None, **kwargs) -> mne.EpochsArray:
        """"""

        if 'montage' in self.header:
            montage = self.header['montage']
        else:
            logging.error("'montage' must be defined in the header.")
            return

        if 'channels' in self.header:
            channels = list(self.header['channels'].values())
        else:
            logging.error("'channels' must be defined in the header.")
            return

        if 'sample_rate' in self.header:
            sampling_rate = self.header['sample_rate']
        else:
            logging.error("'sample_rate' must be defined in the header.")
            return

        # Remove channels that not correspond with the montage
        montage = mne.channels.make_standard_montage(montage)
        channels_names = set(channels).intersection(
            set(montage.ch_names))
        channels_missings = set(channels).difference(
            set(montage.ch_names))

        if channels_missings:
            logging.warning(
                f"Missing {channels_missings} channels in {montage} montage.\n"
                f"Missing channels will be removed from MNE Epochs")

        info = mne.create_info(
            list(channels_names), sfreq=sampling_rate, ch_types="eeg")
        info.set_montage(montage)

        if markers is None:
            markers = self.markers.keys()

        classes = []
        data = []
        for class_ in markers:
            starts = self.markers_relative[class_]
            classes.extend([class_] * len(starts))
            data.extend([self.eeg[:, start + (tmin) * sampling_rate:start + (tmin + duration) * sampling_rate] for start in starts])

        event_id = {e: i for i, e in enumerate(markers)}
        events = [[i, 1, event_id[cls]] for i, cls in enumerate(classes)]

        return mne.EpochsArray(np.array(data), info, events=events, tmin=tmin, event_id=event_id, **kwargs)
