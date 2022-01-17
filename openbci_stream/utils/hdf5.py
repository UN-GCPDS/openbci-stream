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

import os
import json
import shutil
import logging
from functools import wraps
from datetime import datetime, date
from typing import Dict, Any, Optional, Text, List, TypeVar, Union, Tuple

import mne
import tables
import numpy as np
from scipy.interpolate import interp1d

try:
    from functools import cached_property

except ImportError:
    logging.warning('cached_property not found!!')
    logging.warning('Move to Python 3.9 could be a good idea ;)')
    try:
        import asyncio
    except (ImportError, SyntaxError):
        asyncio = None

    class cached_property(object):
        """
        A property that is only computed once per instance and then replaces itself
        with an ordinary attribute. Deleting the attribute resets the property.
        Source: https://github.com/bottlepy/bottle/commit/fa7733e075da0d790d809aa3d2f53071897e6f76
        """  # noqa

        def __init__(self, func):
            self.__doc__ = getattr(func, "__doc__")
            self.func = func

        def __get__(self, obj, cls):
            if obj is None:
                return self

            if asyncio and asyncio.iscoroutinefunction(self.func):
                return self._wrap_in_coroutine(obj)

            value = obj.__dict__[self.func.__name__] = self.func(obj)
            return value

        def _wrap_in_coroutine(self, obj):
            @wraps(obj)
            @asyncio.coroutine
            def wrapper():
                future = asyncio.ensure_future(self.func(obj))
                obj.__dict__[self.func.__name__] = future
                return future

            return wrapper()


try:
    import pyedflib
except Exception as e:
    logging.warning("'pyedflib' is needed for export to EDF")
    logging.warning(e)
# Custom type var
timestamp_ = TypeVar('timesamp', float, np.float)

mne.set_log_level('CRITICAL')


# ----------------------------------------------------------------------
def np2json_serializer(obj):
    """hdf5 handler needs Python classic data types."""
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, datetime):
        return obj.__str__()


# ----------------------------------------------------------------------
def interpolate_datetime(timestamp: List[timestamp_], length: Optional[int] = None) -> List[timestamp_]:
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
        The length of the final timestamp array, if not defined then will be the
        same size of the input timestamp.

    Returns
    -------
    timestamp
        An array with interpolated timestamps.
    """

    if length is None:
        length = timestamp.shape[0]

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

        # self.channels = None
        self._open()

    # ----------------------------------------------------------------------
    def close(self) -> None:
        """Close the file handler.

        Before to close, add some extra values into the header.
        """
        if self.array_eeg is None:
            header2 = {'shape': 0}
            logging.warning('EEG is empty')
        else:
            header2 = {'shape': self.array_eeg.shape}
        # if self.host_ntp:
            # client = ntplib.NTPClient()
            # header2.update(
                # {'end-offset': client.request(self.host_ntp).offset * 1000})

        self.array_hdr.append(
            [json.dumps(header2, default=np2json_serializer)])
        self.f.close()

    # ----------------------------------------------------------------------
    def add_timestamp(self, timestamp: timestamp_) -> None:
        """Add a list of timestamps to the hdf5 file.

        The use of this method is not recommended, instead, it must be used
        `add_eeg` that includes a validation.
        """
        if self.array_dtm is None:
            dim, _ = timestamp.shape
            atom_dtm = tables.Float64Atom()
            self.array_dtm = self.f.create_earray(
                self.f.root, 'timestamp', atom_dtm, shape=(dim, 0), title='EEG timestamp')

        self.array_dtm.append(timestamp)

    # ----------------------------------------------------------------------
    def add_aux_timestamp(self, timestamp: timestamp_) -> None:
        """Add a list of timestamps to the hdf5 file.

        The use of this method is not recommended, instead, it must be used
        `add_aux` that includes a validation.
        """

        if self.array_aux_dtm is None:
            dim, _ = timestamp.shape
            atom_dtm = tables.Float64Atom()
            self.array_aux_dtm = self.f.create_earray(
                self.f.root, 'aux_timestamp', atom_dtm, shape=(dim, 0), title='AUX timestamp')

        self.array_aux_dtm.append(timestamp)

    # ----------------------------------------------------------------------
    def add_header(self, header: Dict[str, Any], host: Optional[str] = None) -> None:
        """Set the header for hdf5 file.

        A header is basically a dictionary with all kinds of useful information.
        There are required keys for some specific methods.

        MNE objects requiere:
          * **montage:** str with montage name, e.g. 'standard_1020'.
          * **channels:** dict with keys as channel index and values as channel
            name, e.g `{1: 'FP1', 2: 'FP2', 3: 'F7'}`.
          * **sample_rate:** int sample rate for acuiered signal, e.g `1000
          * **channels_by_board:** list fo ints with the number of channels
            generated by each board (if multiple boards has been used).

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
        # if host:
            # client = ntplib.NTPClient()
            # header.update(
                # {'start-offset': client.request(host).offset * 1000, })
        # self.host_ntp = host

        self.array_hdr.append(
            [json.dumps(header, default=np2json_serializer)])

    # ----------------------------------------------------------------------
    def add_marker(self, marker: Any, timestamp: timestamp_) -> None:
        """Add a pair of marker-timestamp to the hdf5 file.

        There is some difference between markers and annotations:

          * Markers are writed as time series.
          * Annotations are writed as a list of events.
          * Markers are mainly for repetitions of the same event.
          * Annotations can describe a complex event with a custom duration and
            long description, e.g artifacts.
        """
        self.array_mkr.append(
            [json.dumps([timestamp, marker], default=np2json_serializer)])

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
    def add_annotation(self, onset: timestamp_, duration: int = 0, description: str = '') -> None:
        """Add EDF annotations to the hdf5 file.

        These annotations will be exported with EDF file and follow the format
        defined by `pyedflib <https://pyedflib.readthedocs.io/en/latest/ref/edfwriter.html#pyedflib.EdfWriter.writeAnnotation>`_.

        There is some difference between markers and annotations:

          * Markers are writed as time series.
          * Annotations are writed as a list of events.
          * Markers are mainly for repetitions of the same event.
          * Annotations can describe a complex event with a custom duration and
            long description, e.g artifacts.

        Parameters
        ----------
        onset
            Timestamp for annotation.
        duration
            The duration of the event.
        description
            The description of the annotation.
        """

        self.array_anno.append(
            [json.dumps([onset, duration, description], default=np2json_serializer)])

    # ----------------------------------------------------------------------
    def add_eeg(self, eeg_data: np.ndarray, timestamp: np.ndarray) -> None:
        """Add EEG data to hdf5 file, optionally adds timestamps.

        The first time this method is called the number of channels of EEG is
        configured, and cannot be changed.

        Parameters
        ----------
        eeg_data
            An array of shape (`channels, time`)
        timestamp
            The timestamp for this data.
        """
        if self.array_eeg is None:
            self.channels, _ = eeg_data.shape
            atom_eeg = tables.Float64Atom()
            self.array_eeg = self.f.create_earray(
                self.f.root, 'eeg_data', atom_eeg, shape=(self.channels, 0), title='EEG time series')

        if self.channels != eeg_data.shape[0]:
            logging.warning(
                f'The number of channels {self.channels} can not be changed!')
            return

        self.array_eeg.append(eeg_data)

        # if isinstance(timestamp, (np.ndarray, list, tuple)):

        assert timestamp.shape[1] == eeg_data.shape[
            1], f"Is not recommended add data and timestamp from different sizes. {len(timestamp)} != {eeg_data.shape[1]}"
        self.add_timestamp(timestamp)

        # elif timestamp != None:
            # timestamp_ = np.zeros(eeg_data.shape[1])
            # timestamp_[-1] = timestamp
            # self.add_timestamp(timestamp_)

    # ----------------------------------------------------------------------
    def add_aux(self, aux_data: np.ndarray, timestamp: np.ndarray) -> None:
        """Write AUX data into the hdf5 file.

        The shape of aux data cannot be changed after the first write.

        Parameters
        ----------
        aux_data
            OpenBCI aux data defined in `board modes <../notebooks/04-board_modes.ipynb>`_
        timestamp
            The timestamp for this data.
        """

        if self.array_aux is None:
            channels, _ = aux_data.shape
            atom_eeg = tables.Float64Atom()
            self.array_aux = self.f.create_earray(
                self.f.root, 'aux_data', atom_eeg, shape=(channels, 0), title='Auxiliar data')

        try:
            self.array_aux.append(aux_data)

            assert timestamp.shape[1] == aux_data.shape[1], f"Is not\
            recommended add data and timestamp from different sizes.\
            {len(timestamp)} != {aux_data.shape[1]}"
            self.add_aux_timestamp(timestamp)

        except Exception as e:
            logging.warning(e)

    # ----------------------------------------------------------------------
    def __enter__(self) -> None:
        """"""
        return self

    # ----------------------------------------------------------------------
    def _open(self) -> None:
        """"""
        self.f = tables.open_file(self.filename, mode='w')

        atom_json = tables.StringAtom(itemsize=2**15)

        self.array_hdr = self.f.create_earray(
            self.f.root, 'header', atom_json, shape=(0,), title='HEADER')
        self.array_eeg = None
        self.array_aux = None
        self.array_dtm = None
        self.array_aux_dtm = None
        self.array_mkr = self.f.create_earray(
            self.f.root, 'markers', atom_json, shape=(0,), title='EEG markers')
        self.array_anno = self.f.create_earray(
            self.f.root, 'annotations', atom_json, shape=(0,), title='EEG annotations')

    # ----------------------------------------------------------------------
    def __exit__(self, exc_type: Text, exc_val: Text, exc_tb: Text) -> None:
        """"""
        self.close()


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
        self.offsets_position = None
        self.aux_offsets_position = None
        self._open()

    # ----------------------------------------------------------------------
    def __repr__(self):
        """"""
        sep = "=" * 10

        info = sep
        info += f"\n{self.filename}\n"
        info += str(datetime.fromtimestamp(self.header['datetime']))
        info += '\n' + sep + '\n'
        info += f'MARKERS: {list(self.markers.keys())}\n'
        for k in self.header:
            info += f"{k.upper()}: {self.header[k]}\n"
        info += sep
        return info

    # ----------------------------------------------------------------------
    @cached_property
    def header(self) -> Dict[str, Any]:
        """The header of the hdf file."""
        header = json.loads(self.f.root.header[0])
        header.update(json.loads(self.f.root.header[1]))
        if 'channels' in header:
            header['channels'] = {int(k): header['channels'][k]
                                  for k in header['channels']}
        return header

    # ----------------------------------------------------------------------
    @cached_property
    def eeg(self) -> np.ndarray:
        """The EEG data of the hdf file in the shape of (`channels, time`)."""
        eeg_ = np.array(self.f.root.eeg_data).T

        if self.offsets_position is None:
            _ = self.timestamp

        eeg__ = []
        ch = 0
        for pos, nchan in zip(self.offsets_position, self.header['channels_by_board']):
            for _ in range(nchan):
                eeg__.append(np.roll(eeg_[ch], -pos))
                ch += 1
        if len(self.offsets_position) > 1:
            return np.array(eeg__)[:, :-max(self.offsets_position)]
        return np.array(eeg__)

    # ----------------------------------------------------------------------
    @cached_property
    def aux(self) -> np.ndarray:
        """The AUX data of the hdf file in the shape of (`aux, time`)."""
        aux_ = np.array(self.f.root.aux_data).T

        if self.aux_offsets_position is None:
            _ = self.aux_timestamp

        aux__ = []
        ch = 0
        split = [aux_.shape[0] / len(self.header['channels_by_board'])] * \
            len(self.header['channels_by_board'])
        for pos, nchan in zip(self.aux_offsets_position, split):
            for _ in range(int(nchan)):
                aux__.append(np.roll(aux_[ch], -pos))
                ch += 1
        if len(self.aux_offsets_position) > 1:
            return np.array(aux__)[:, :-max(self.aux_offsets_position)]
        return np.array(aux__)

    # ----------------------------------------------------------------------
    @cached_property
    def annotations(self) -> list:
        """A list of annotations.

        The `HDF5Writer` write the annotations with timestamps, but `EDF` needs
        the relative time from start in seconds.
        """

        if not hasattr(self.f.root, 'annotations'):
            return []

        anotations = [json.loads(an) for an in self.f.root.annotations]
        start = datetime.fromtimestamp(self.timestamp[0][0])

        for index, an in enumerate(anotations):
            onset = (datetime.fromtimestamp(an[0]) - start).total_seconds()
            anotations[index][0] = onset

        return anotations

    # ----------------------------------------------------------------------
    @cached_property
    def markers(self) -> Dict[str, List[timestamp_]]:
        """A dictionary with the markers and timestamps as values."""

        if not hasattr(self.f.root, 'markers'):
            return {}

        _ = self.timestamp

        markers = {}
        for mkr in self.f.root.markers:
            t, marker = json.loads(mkr)
            # markers.setdefault(marker, []).append(np.abs(self.timestamp - ((t * 1000) - self.timestamp_offset)).argmin())
            markers.setdefault(marker, []).append(
                np.abs(self.timestamp - ((t - self.timestamp_offset) * 1000)).argmin())

        return markers

    # # ----------------------------------------------------------------------
    # @cached_property
    # def markers_relative(self) -> Dict[str, List[int]]:
        # """A dictionary with the markers and milliseconds as values."""
        # markers_relative = {}
        # for key in self.markers:
            # locs = self.markers[key]
            # markers_relative[key] = [
                # np.abs(self.timestamp - loc).argmin() for loc in locs]

        # return markers_relative

    # ----------------------------------------------------------------------
    @cached_property
    def timestamp(self) -> List[timestamp_]:
        """A list of timestamps for EEG data."""

        timestamp = self.f.root.timestamp

        if timestamp.shape[0] > 1:
            target = timestamp[:, 0].max()
            self.offsets_position = [
                np.argmin(abs(ts - target)) for ts in timestamp[:timestamp.shape[0]]]
            t = timestamp[:, :-max(self.offsets_position)
                          ].mean(axis=0) * 1000
            self.timestamp_offset = t[0]
            return (t - self.timestamp_offset)

        self.timestamp_offset = timestamp[0][0]
        self.offsets_position = [0]
        return (np.array(timestamp).reshape(1, -1) - self.timestamp_offset) * 1000

    # ----------------------------------------------------------------------
    @cached_property
    def aux_timestamp(self) -> List[timestamp_]:
        """A list of timestamps for EEG data."""

        timestamp = self.f.root.aux_timestamp

        if timestamp.shape[0] > 1:
            target = timestamp[:, 0].max()
            self.aux_offsets_position = [
                np.argmin(abs(ts - target)) for ts in timestamp[:timestamp.shape[0]]]
            t = timestamp[:, :-max(self.aux_offsets_position)
                          ].mean(axis=0) * 1000
            self.aux_timestamp_offset = t[0]
            return (t - self.aux_timestamp_offset)

        self.aux_timestamp_offset = timestamp[0][0]
        self.aux_offsets_position = [0]
        return (np.array(timestamp).reshape(1, -1) - self.aux_timestamp_offset) * 1000

    # # ----------------------------------------------------------------------
    # @cached_property
    # def array_timestamp(self) -> List[timestamp_]:
        # """A list of timestamps for EEG data."""

        # timestamp = self.f.root.timestamp
        # target = timestamp[:, 0].max()
        # self.offsets_position = [
            # np.argmin(abs(ts - target)) for ts in timestamp[:timestamp.shape[0]]]

        # return timestamp[:, :-max(self.offsets_position)]

    # # ----------------------------------------------------------------------
    # @cached_property
    # def timestamp_relative(self, fast=False) -> List[int]:
        # """A list of timestamps in milliseconds.

        # If `fast` the a simple relation between sample rate and data length is
        # calculate instead.
        # """
        # return self.timestamp

        # # if fast:
            # # return np.linspace(0, (self.eeg.shape[1] / self.header['sample_rate']) * 1000, self.eeg.shape[1])
        # # else:
            # # m = (self.timestamp - self.timestamp[0]) * 1e3
            # # return np.array(np.round(m), dtype=int)

    # ----------------------------------------------------------------------

    @cached_property
    def classes(self):
        """A list with the same length of EEG with markers as numbers."""
        classes = np.zeros(self.timestamp.shape)
        for marker in self.markers:
            classes[self.markers[marker]
                    ] = self.classes_indexes[marker]
        return classes

    # # ----------------------------------------------------------------------
    # @cached_property
    # def aux_timestamp_(self) -> List[timestamp_]:
        # """A list of timestamps for AUX data."""
        # return self._timestamp(self.aux.shape[1])

    # # ----------------------------------------------------------------------
    # def _timestamp(self) -> List[timestamp_]:
        # """Interpolate the timestamps in the case of zeros in it."""
        # timestamp = self.f.root.timestamp

        # # if timestamp[timestamp == 0].size > 0:
            # # timestamp = interpolate_datetime(timestamp, length)

        # return timestamp

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
    def get_epochs(self, tmax: int, tmin: Optional[int] = 0, markers: Union[None, List[str]] = None, preprocess=None, eeg=None, **kwargs) -> mne.EpochsArray:
        """Create an `EpochsArray` object with the `MNE` library.

        This method auto crop the data in regard to markers also will drop
        channels that no correspond with the montage. For an example of use
        refer to `Data storage handler - MNE objects<../notebooks/07-data_storage_handler.html#MNE-objects>`_

        Parameters
        ----------
        duration
            The duration of the trial, in seconds.
        tmin
            The time to take previous to the marker, in seconds.
        markers
            A filter of markers for crop the signal.
        kwargs
            Optional arguments passed to `EpochsArray <https://mne.tools/stable/generated/mne.EpochsArray.html>`_

        Returns
        -------
        epochs
            An MNE Epochs object.
        """
        if eeg is None:
            eeg = self.eeg

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
        no_fit = 0
        for class_ in markers:
            starts = self.markers[class_]

            for start in starts:
                i0 = int(start + (tmin * sampling_rate))
                i1 = int(start + (tmax * sampling_rate))

                if i1 < eeg.shape[1]:
                    data.append(eeg[:, i0:i1])
                    classes.append(class_)
                else:
                    no_fit += 1
        if no_fit:
            logging.warning(
                f'{no_fit} trials have markers but not EEG data associated.')

        event_id = {mk: self.classes_indexes[mk] for mk in markers}
        events = [[i, 1, event_id[cls]] for i, cls in enumerate(classes)]

        length = (tmax * sampling_rate) - (tmin * sampling_rate)
        data = list(filter(lambda d: d.shape[-1] == int(length), data))

        if preprocess:
            data = preprocess(np.array(data))
        else:
            data = np.array(data)

        # raw = mne.io.RawArray(data, info, first_samp=0,
                              # copy='auto', verbose=None)
        # return mne.Epochs(raw, events=events, tmin=tmin, event_id=event_id, **kwargs)

        return mne.EpochsArray(data, info, events=events, tmin=tmin, event_id=event_id, **kwargs)

    # ----------------------------------------------------------------------
    def to_edf(self, filename: str, eeg=None) -> None:
        """Export to EDF file."""
        if eeg is None:
            eeg = self.eeg

        if 'sample_rate' in self.header:
            sampling_rate = self.header['sample_rate']
        else:
            logging.error("'sample_rate' must be defined in the header.")
            return

        edf_channel_info = []
        edf_data_list = []

        for i, channel in enumerate(self.header['channels']):
            data = eeg[i]
            if data.max() == data.min():
                max_, min_ = 1, -1
            else:
                max_, min_ = data.max(), data.min()
            channel = {
                'label': f"ch{i+1} - {self.header['channels'][channel]}",
                'dimension': 'uV',
                'sample_rate': sampling_rate,
                'physical_max': max_,
                'physical_min': min_,
                'digital_max': 2 ** 12,
                'digital_min': -2 ** 12,
                'transducer': '',
                'prefilter': '',
            }
            edf_channel_info.append(channel)
            edf_data_list.append(data)

        for i, aux in enumerate(self.aux):
            if aux.max() == aux.min():
                max_, min_ = 1, -1
            else:
                max_, min_ = aux.max(), aux.min()
            channel = {
                'label': f"aux{i+1}",
                'dimension': '',
                'sample_rate': sampling_rate,
                'physical_max': max_,
                'physical_min': min_,
                'digital_max': 2 ** 12,
                'digital_min': -2 ** 12,
                'transducer': '',
                'prefilter': '',
            }
            edf_channel_info.append(channel)
            edf_data_list.append(aux)

        if self.markers:
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
            'startdate': datetime.fromtimestamp(self.timestamp[0][0]),
            'technician': self.header.get('technician', ''),
        }

        f = pyedflib.EdfWriter(filename, len(
            edf_channel_info), file_type=pyedflib.FILETYPE_EDFPLUS)

        f.setHeader(header)
        f.setSignalHeaders(edf_channel_info)
        f.writeSamples(edf_data_list)

        for annotation in self.annotations:
            f.writeAnnotation(*annotation)
        f.close()

    # ----------------------------------------------------------------------
    def get_data(self, tmax: int, tmin: Optional[int] = 0, markers: Union[None, List[str]] = None, eeg=None, preprocess=None, **kwargs) -> Tuple[np.ndarray]:
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
        trials
            Dataset with the shape (`trials`, `channels`, `time`)
        classes
            List of classes
        """

        epochs = self.get_epochs(
            tmax, tmin, markers, eeg=eeg, preprocess=preprocess)
        return epochs._data, epochs.events[:, 2]

    # # ----------------------------------------------------------------------
    # @cached_property
    # def offset(self) -> float:
        # """Calculate the timestamps offset in seconds."""
        # if self.offset_correction and 'start-offset' in self.header and 'end-offset' in self.header:
            # start, end = self.header['start-offset'], self.header['end-offset']
            # return (start + (start - end) / self.header['shape'][1]) / 1000
        # else:
            # if self.offset_correction:
                # logging.info('No offsets values to perform correction')
            # return 0

    # ----------------------------------------------------------------------
    def to_npy(self, filename, eeg=None, tmin=None, tmax=None):
        """"""
        if eeg is None:
            eeg = self.eeg

        filename = os.path.abspath(filename)
        tmp_dir = os.path.join(os.path.dirname(filename), 'tmp_dir_npy')
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)
        os.mkdir(tmp_dir)

        if (tmin is None) and (tmax is None):
            np.save(os.path.join(tmp_dir, 'eeg'), eeg)
            np.save(os.path.join(tmp_dir, 'timestamp'), self.timestamp)
        else:
            eeg_, classes = self.get_data(eeg, tmin=tmin, tmax=tmax)
            np.save(os.path.join(tmp_dir, 'eeg'), eeg_)
            np.save(os.path.join(tmp_dir, 'classes'), classes)

        np.save(os.path.join(tmp_dir, 'markers'), self.markers)
        np.save(os.path.join(tmp_dir, 'aux'), self.aux)
        np.save(os.path.join(tmp_dir, 'aux_timestamp'), self.aux_timestamp)
        np.save(os.path.join(tmp_dir, 'metadata'), self.header)

        shutil.make_archive(filename, 'zip', tmp_dir)

    # ----------------------------------------------------------------------
    def get_rises(self, signal, timestamp, lower, upper):
        """"""
        raw = signal.copy()

        raw[raw < lower] = 1e5
        raw[raw > upper] = 1e5
        raw = raw - raw.min()
        raw[raw > 1e4] = raw.min()

        # raw[raw <= raw.mean()] = 0
        # raw[raw > raw.mean()] = 1
        m = (raw.max() - raw.min()) / 2
        raw[raw <= m] = 0
        raw[raw > m] = 1

        raw = np.diff(raw, prepend=0)
        raw[raw < 0] = 0

        return timestamp[raw == 1]

    # ----------------------------------------------------------------------
    def fix_markers(self, target_markers, rises, range_=2000):
        """"""
        global_ = {}
        for mk in target_markers:

            offsets = []
            for m in self.markers[mk]:
                Q = rises[abs(rises - m).argmin()]
                if abs(Q - m) < range_:
                    offsets.append([m, Q])

            offsets = np.array(offsets)
            self.markers[f'{mk}_fixed'] = offsets[:, 1]
            global_[mk] = np.median(np.diff(offsets))

        return global_
