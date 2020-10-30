"""
====================
Data storage handler
====================

This data handler use [PyTables](https://www.pytables.org/) that is built on top
of the HDF5 library, using the Python language and the NumPy package. It
features an object-oriented interface that, combined with C extensions for the
performance-critical parts of the code (generated using Cython), makes it a
fast, yet extremely easy to use tool for interactively browse, process and
search very large amounts of data. One important feature of
[PyTables](https://www.pytables.org/) is that it optimizes memory and disk
resources so that data takes much less space (specially if on-flight compression
is used) than other solutions such as relational or object oriented databases.

For examples and descriptions refers to documentation:
`Data storage handler <../07-data_storage_handler.ipynb>`_
"""

import json
import logging
from datetime import datetime, date
from functools import cached_property
from typing import Dict, Any, Optional, Text, List, TypeVar, Union

import mne
import tables
import pyedflib
import numpy as np
from scipy.interpolate import interp1d

# Custom type var
timestamp_ = TypeVar('timesamp', float, np.float)


# ----------------------------------------------------------------------
def np2json_serializer(obj):
    """hdf5 handler needs Python classic data types."""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, datetime):
        return obj.__str__()


# ----------------------------------------------------------------------
def interpolate_datetime(timestamp: List[timestamp_], length: int) -> List[timestamp_]:
    """Interpolate uncomplete timestamp list.

    The input timestamp list must be a list of timestamps separated by zeros,
    this script will complete the missing timestamps. This primary purpose is to
    complete the list generated from stream data when only it has a sample rate
    and acquired times.

    Parameters
    ----------
    timestamp
        An array with timestamps and zeros.
    length
        The length of the final timestamp array

    Returns
    -------
    timestamp
        An array with interpolated timestamps.
    """

    nonzero = np.nonzero(timestamp)[0]
    x = nonzero * (length / nonzero[-1])
    interp = interp1d(x, timestamp[nonzero], fill_value="extrapolate")
    # args = np.arange(-nonzero[0], length - nonzero[0])
    args = np.arange(length)

    timestamp = interp(args)
    return timestamp


########################################################################
class HDF5Writer:
    """This HDF5 data handler was pre-configured for the architecture of
    acquired EEG data.

    This module can be used like an instance e.g.

    >>> writer = HDF5Writer('file.h5')
    >>> writer.add_marker('LEFT', datetime.now().timestamp())
    >>> writer.close()

    or can be used with the `with` control-flow structure e.g.

    >>> with HDF5Writer('file.h5') as write:
            writer.add_marker('LEFT', datetime.now().timestamp())

    Parameters
    ----------
    filename
        Path where the edf file will be created.
    """

    # ----------------------------------------------------------------------
    def __init__(self, filename: str) -> None:
        """"""
        if filename.endswith('h5'):
            self.filename = f'{filename}'
        else:
            self.filename = f'{filename}.h5'

        self.channels = None
        self._open()

    # ----------------------------------------------------------------------
    def close(self) -> None:
        """Close the file handler."""
        self.f.close()

    # ----------------------------------------------------------------------
    def add_timestamp(self, timestamp: timestamp_) -> None:
        """Add a list of timestamps to the hdf5 file.

        The use of this method is not recommended, instead, it must be used
        `add_eeg` that includes a validation.
        """
        self.array_dtm.append(timestamp)

    # ----------------------------------------------------------------------
    def add_header(self, header: Dict[str, Any]) -> None:
        """Set the header for hdf5 file.

        A header is basically a dictionary with all kinds of useful information.
        There are required keys for some specific methods.

        MNE objects requiere:
          * **montage:** str with montage name, e.g. 'standard_1020'.
          * **channels:** dict with keys as channel index and values as channel
            name, e.g `{1: 'FP1', 2: 'FP2', 3: 'F7'}`.
          * **sample_rate:** int sample rate for acuiered signal, e.g `1000`.

        EDF objects requiere (In addition to the above):
          * **admincode:** str with the admincode.
          * **birthdate:** date object with the the birthdate of the patient.
          * **equipment:** str thats describes the measurement equpipment.
          * **gender:** int with the the gender, 1 is male, 0 is female.
          * **patientcode:** str with the patient code.
          * **patientname:** str with the patient name.
          * **patient_additional:** str with the additional patient information.
          * **recording_additional:** str wit the additional recording information.
          * **technician:** str with the technicians name.
        """

        self.array_hdr.append([json.dumps(header, default=np2json_serializer)])

    # ----------------------------------------------------------------------
    def add_marker(self, marker: Any, timestamp: timestamp_) -> None:
        """Add a pair of marker-timestamp to the hdf5 file."""
        self.array_mkr.append([json.dumps([timestamp, marker], default=np2json_serializer)])

    # ----------------------------------------------------------------------
    def add_markers(self, markers: Dict[str, List[timestamp_]]) -> None:
        """Add a set of markers to the hdf5 file.

        This method is used to write a set of markers at the same time, works
        with a dictionary object, with keys as marker and values as a list of
        timestamps

        Example
        -------

        >>> markes = {'LEFT': [1603898187.226709,
                               1603898197.226709,
                               1603898207.226709],
                      'RIGHT': [1603898192.226709,
                                1603898202.226709,
                                1603898212.226709]
                      }
        >>> add_markers(markers)
        """

        for marker in markers:
            for timestamp in markers[marker]:
                self.add_marker(marker, timestamp)

    # ----------------------------------------------------------------------
    def add_annotation(self, onset: int, duration: int = 0, description: str = '') -> None:
        """Add EDF annotations to the hdf5 file.

        These annotations will be exported with EDF file and follow the format
        defined by `pyedflib <https://pyedflib.readthedocs.io/en/latest/ref/edfwriter.html#pyedflib.EdfWriter.writeAnnotation>`_.
        """
        self.array_anno.append([json.dumps([onset, duration, description], default=np2json_serializer)])

    # ----------------------------------------------------------------------
    def add_eeg(self, eeg_data: np.ndarray, timestamp: Optional[timestamp_] = None) -> None:
        """Add EEG data to hdf5 file, optionally adds timestamps.

        The first time this method is called the number of channels of EEG is
        configured, and cannot be changed.

        Parameters
        ----------
        eeg_data
            An array of shape (`channels, time`)
        timestamp
            A single timestamp corresponding to the last sample acquired.
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
        """Write AUX data into the hdf5 file.

        The shape of aux data cannot be changed after the first write.

        Parameters
        ----------
        aux_data
            OpenBCI aux data defined in `board modes <../notebooks/04-board_modes.ipynb>`_
        """

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


########################################################################
class HDF5Reader:
    """Objects created with `HDF5Writer` can be opened with `HDF5Reader`.

    This class support export to other formmats like
    `MNE epochs <https://mne.tools/stable/generated/mne.Epochs.html>`_
    and `EDF <https://www.edfplus.info/>`_.


    Parameters
    ----------
    filename
        Path with the location of the hdf file.
    """

    # ----------------------------------------------------------------------
    def __init__(self, filename: str) -> None:
        """"""
        self.filename = filename
        self._open()

    # ----------------------------------------------------------------------
    @cached_property
    def header(self) -> Dict[str, Any]:
        """The header of the hdf file."""
        header = json.loads(self.f.root.header[0])
        if 'channels' in header:
            header['channels'] = {int(k): header['channels'][k] for k in header['channels']}
        return header

    # ----------------------------------------------------------------------
    @cached_property
    def eeg(self) -> np.ndarray:
        """The EEG data of the hdf file in the shape of (`channels, time`)."""
        return np.array(self.f.root.eeg_data).T

    # ----------------------------------------------------------------------
    @cached_property
    def aux(self) -> np.ndarray:
        """The AUX data of the hdf file in the shape of (`aux, time`)."""
        return np.array(self.f.root.aux_data).T

    # ----------------------------------------------------------------------
    @cached_property
    def annotations(self) -> list:
        """A list of annotations."""
        return [json.loads(anno) for anno in self.f.root.annotations]

    # ----------------------------------------------------------------------
    @cached_property
    def markers(self) -> Dict[str, List[timestamp_]]:
        """A dictionary with the markers and timestamps as values."""
        markers = {}
        for mkr in self.f.root.markers:
            t, marker = json.loads(mkr)
            markers.setdefault(marker, []).append(t)

        return markers

    # ----------------------------------------------------------------------
    @cached_property
    def markers_relative(self) -> Dict[str, List[int]]:
        """A dictionary with the markers and milliseconds as values."""
        markers_relative = {}
        for key in self.markers:
            locs = self.markers[key]
            markers_relative[key] = [self.timestamp_relative[np.abs(self.timestamp - loc).argmin() + 1] for loc in locs]

        return markers_relative

    # ----------------------------------------------------------------------
    @cached_property
    def timestamp(self) -> List[timestamp_]:
        """A list of timestamps for EEG data."""
        return self._timestamp(self.eeg.shape[1])

    # ----------------------------------------------------------------------
    @cached_property
    def timestamp_relative(self) -> List[int]:
        """A list of timestamps in milliseconds."""
        m = (self.timestamp - self.timestamp[0]) * 1e3
        return np.array(np.round(m), dtype=int)

    # ----------------------------------------------------------------------
    @cached_property
    def classes(self):
        """A list with the same length of EEG with markers as numbers."""
        classes = np.zeros(self.timestamp_relative.shape)
        for marker in self.markers_relative:
            classes[self.markers_relative[marker]] = self.classes_indexes[marker]
        return classes

    # ----------------------------------------------------------------------
    @cached_property
    def aux_timestamp_(self) -> List[timestamp_]:
        """A list of timestamps for AUX data."""
        return self._timestamp(self.aux.shape[1])

    # ----------------------------------------------------------------------
    def _timestamp(self, length: int) -> List[timestamp_]:
        """Interpolate the timestamps in the case of zeros in it."""
        timestamp = self.f.root.timestamp

        if timestamp[timestamp == 0].size > 0:
            timestamp = interpolate_datetime(timestamp, length)
        return timestamp

    # ----------------------------------------------------------------------
    @cached_property
    def classes_indexes(self) -> Dict[str, int]:
        """The standard for classes and indexes."""
        return {key: (i + 1) for i, key in enumerate(self.markers.keys())}

    # ----------------------------------------------------------------------
    def __enter__(self) -> None:
        """"""
        return self

    # ----------------------------------------------------------------------
    def _open(self) -> None:
        """"""
        self.f = tables.open_file(self.filename, mode='r')

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
        """Create an `EpochsArray` object with the `MNE` library.

        This method auto crop the data in regard to markers also will drop
        channels that no correspond with the montage. For an example of use
        refer to `Data storage handler - MNE objects<../notebooks/07-data_storage_handler.html#MNE-objects>`_

        Parameters
        ----------
        duration
            The duration of the trial.
        tmin
            The time to take previous to the marker.
        markers
            A filter of markers for crop the signal.
        kwargs
            Optional arguments passed to `EpochsArray <https://mne.tools/stable/generated/mne.EpochsArray.html>`_

        Returns
        -------
        epochs
            An MNE Epochs object.
        """

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
            markers = self.classes_indexes.keys()

        classes = []
        data = []
        for class_ in markers:
            starts = self.markers_relative[class_]
            classes.extend([class_] * len(starts))
            data.extend([self.eeg[:, start + (tmin) * sampling_rate:start + (tmin + duration) * sampling_rate] for start in starts])

        event_id = {mk: self.classes_indexes[mk] for mk in markers}
        events = [[i, 1, event_id[cls]] for i, cls in enumerate(classes)]

        return mne.EpochsArray(np.array(data), info, events=events, tmin=tmin, event_id=event_id, **kwargs)

    # ----------------------------------------------------------------------
    def to_edf(self, filename: str) -> None:
        """Export to EDF file."""

        if 'sample_rate' in self.header:
            sampling_rate = self.header['sample_rate']
        else:
            logging.error("'sample_rate' must be defined in the header.")
            return

        edf_channel_info = []
        edf_data_list = []

        for i, channel in enumerate(self.header['channels']):
            data = self.eeg[i]
            channel = {
                'label': f"ch{i+1} - {self.header['channels'][channel]}",
                'dimension': 'uV',
                'sample_rate': sampling_rate,
                'physical_max': data.max(),
                'physical_min': data.min(),
                'digital_max': 2 ** 12,
                'digital_min': -2 ** 12,
                'transducer': '',
                'prefilter': '',
            }
            edf_channel_info.append(channel)
            edf_data_list.append(data)

        for i, aux in enumerate(self.aux):
            channel = {
                'label': f"aux{i+1}",
                'dimension': '',
                'sample_rate': sampling_rate,
                'physical_max': aux.max(),
                'physical_min': aux.min(),
                'digital_max': 2 ** 12,
                'digital_min': -2 ** 12,
                'transducer': '',
                'prefilter': '',
            }
            edf_channel_info.append(channel)
            edf_data_list.append(aux)

        channel = {
            'label': f"classes",
            'dimension': '',
            'sample_rate': sampling_rate,
            'physical_max': max(self.classes_indexes.values()),
            'physical_min': min(self.classes_indexes.values()),
            'digital_max': 2 ** 12,
            'digital_min': -2 ** 12,
            'transducer': '',
            'prefilter': '',
        }
        edf_channel_info.append(channel)
        edf_data_list.append(self.classes)

        header = {
            'admincode': self.header.get('admincode', ''),
            'birthdate': self.header.get('birthdate', date(1991, 2, 8)),
            'equipment': self.header.get('equipment', ''),
            'gender': self.header.get('gender', 0),
            'patientcode': self.header.get('patientcode', ''),
            'patientname': self.header.get('patientname', ''),
            'patient_additional': self.header.get('patient_additional', ''),
            'recording_additional': self.header.get('recording_additional', ''),
            'startdate': datetime.fromtimestamp(self.timestamp[0]),
            'technician': self.header.get('technician', ''),
        }

        f = pyedflib.EdfWriter(filename, len(edf_channel_info), file_type=pyedflib.FILETYPE_EDFPLUS)

        f.setHeader(header)
        f.setSignalHeaders(edf_channel_info)
        f.writeSamples(edf_data_list)

        for annotation in self.annotations:
            f.writeAnnotation(*annotation)
        f.close()
