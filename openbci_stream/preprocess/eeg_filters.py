"""
===========
EEG Filters
===========

Predefined filter.

"""

from scipy import signal
import numpy as np
from functools import lru_cache
from datetime import datetime
from abc import ABCMeta, abstractmethod
import logging

DEFAULT_FS = 250
LOG_SPACE = np.logspace(np.log10(10), np.log10(16000), 1000)


########################################################################
class Filter(metaclass=ABCMeta):
    """Generic filter."""

    # ----------------------------------------------------------------------
    # def __call__(self, eeg, /, axis=None, timestamp=None, fs=None, padtype='even', padlen=None, method='pad', irlen=None):
    def __call__(self, eeg, axis=None, timestamp=None, fs=None, padtype='even', padlen=None, method='pad', irlen=None):
        """
        Apply a digital filter forward and backward to a signal.

        This function applies a linear digital filter twice, once forward and
        once backwards.  The combined filter has zero phase and a filter order
        twice that of the original.

        The function provides options for handling the edges of the signal.

        Parameters
        ----------

        eeg: array
            Numpy array to filter.
        axis : int, optional
            The axis of `x` to which the filter is applied.
            Default is None, in this case is selected automatically, with the
            larger dimension as time.
        timestamp: array, optional.
            The time vector for calculate the sample frequency.
        fs: float, optional.
            The sample frequency if timestamp is not defined.
        padtype : str or None, optional
            Must be 'odd', 'even', 'constant', or None.  This determines the
            type of extension to use for the padded signal to which the filter
            is applied.  If `padtype` is None, no padding is used.  The default
            is 'odd'.
        padlen : int or None, optional
            The number of elements by which to extend `x` at both ends of
            `axis` before applying the filter.  This value must be less than
            ``x.shape[axis] - 1``.  ``padlen=0`` implies no padding.
            The default value is ``3 * max(len(a), len(b))``.
        method : str, optional
            Determines the method for handling the edges of the signal, either
            "pad" or "gust".  When `method` is "pad", the signal is padded; the
            type of padding is determined by `padtype` and `padlen`, and `irlen`
            is ignored.  When `method` is "gust", Gustafsson's method is used,
            and `padtype` and `padlen` are ignored.
        irlen : int or None, optional
            When `method` is "gust", `irlen` specifies the length of the
            impulse response of the filter.  If `irlen` is None, no part
            of the impulse response is ignored.  For a long signal, specifying
            `irlen` can significantly improve the performance of the filter.

        Returns
        -------
        y : ndarray
            The filtered output with the same shape as `x`.

        See Also
        --------
        sosfiltfilt, lfilter_zi, lfilter, lfiltic, savgol_filter, sosfilt

        Notes
        -----
        When `method` is "pad", the function pads the data along the given axis
        in one of three ways: odd, even or constant.  The odd and even extensions
        have the corresponding symmetry about the end point of the data.  The
        constant extension extends the data with the values at the end points. On
        both the forward and backward passes, the initial condition of the
        filter is found by using `lfilter_zi` and scaling it by the end point of
        the extended data.

        When `method` is "gust", Gustafsson's method [1]_ is used.  Initial
        conditions are chosen for the forward and backward passes so that the
        forward-backward filter gives the same result as the backward-forward
        filter.

        The option to use Gustaffson's method was added in scipy version 0.16.0.
        """

        if axis is None:
            if eeg.shape[0] > eeg.shape[1]:
                axis = 0
            else:
                axis = 1

        timestamp = np.array(timestamp)

        if timestamp.any():
            self._fit_fs(eeg=eeg, timestamp=timestamp)
        elif fs:
            self._fit_fs(fs=fs)

        return signal.filtfilt(self._b, self._a, eeg, axis=axis, padtype=padtype, padlen=padlen, method=method, irlen=irlen)

    # ----------------------------------------------------------------------
    @abstractmethod
    def _fit(self):
        """"""
        pass

    # ----------------------------------------------------------------------
    # def _fit_fs(self, /, eeg=None, timestamp=None, fs=None):
    def _fit_fs(self, eeg=None, timestamp=None, fs=None):
        """Compile filters for new sample frequency."""
        if fs is None:
            if isinstance(timestamp[-1], (int, float)):
                delta = datetime.fromtimestamp(
                    timestamp[-1]) - datetime.fromtimestamp(timestamp[0])
            else:
                delta = timestamp[-1] - timestamp[0]
            fs = max(eeg.shape) / delta.total_seconds()

        fs = LOG_SPACE[abs(LOG_SPACE - fs).argmin()]
        self._b, self._a = self._fit(fs)


########################################################################
class FiltersChain:
    """Join a set of filters and call one after the other."""

    # ----------------------------------------------------------------------
    def __init__(self, *filters):
        """"""
        self.filters = filters

    # ----------------------------------------------------------------------
    def __call__(self, eeg, *args, **kwargs):
        """"""
        for filter_ in self.filters:
            eeg = filter_(eeg, *args, **kwargs)
        return eeg


########################################################################
class GenericNotch(Filter):
    """Neneric notch."""

    # ----------------------------------------------------------------------
    # def __init__(self, / , f0, fs, Q=3):
    def __init__(self, f0, fs, Q=3):
        """Design second-order IIR notch digital filter.

        A notch filter is a band-stop filter with a narrow bandwidth
        (high quality factor). It rejects a narrow frequency band and
        leaves the rest of the spectrum little changed.

        Parameters
        ----------
        f0 : float
            Frequency to remove from a signal. If `fs` is specified, this is in
            the same units as `fs`. By default, it is a normalized scalar that must
            satisfy  ``0 < w0 < 1``, with ``w0 = 1`` corresponding to half of the
            sampling frequency.
        Q : float
            Quality factor. Dimensionless parameter that characterizes
            notch filter -3 dB bandwidth ``bw`` relative to its center
            frequency, ``Q = w0/bw``.
        fs : float, optional
            The sampling frequency of the digital system.
        """

        self.f0, self.Q = f0, Q
        self._b, self._a = self._fit(fs)

    # ----------------------------------------------------------------------
    @lru_cache(maxsize=700)
    def _fit(self, fs):
        """Get the numerator and denominator of new sample frequency.

        Parameters
        ----------
        fs : float
            The sampling frequency of the digital system.

        Returns
        -------
        b, a : ndarray, ndarray
            Numerator (``b``) and denominator (``a``) polynomials
            of the IIR filter.
        """
        if fs != DEFAULT_FS:
            logging.info(f"Compiled `Notch` filter for {fs:0.2f} Hz")
        return signal.iirnotch(self.f0, self.Q, fs)


########################################################################
class GenericButterBand(Filter):
    """Generic bandpass"""

    # ----------------------------------------------------------------------
    # def __init__(self, / , f0, f1, fs , N=3):
    def __init__(self, f0, f1, fs, N=3):
        """Butterworth digital and analog filter design.

        Design an Nth-order digital or analog Butterworth filter and return
        the filter coefficients.

        Parameters
        ----------
        f0: float
            Low cutoff frequency.
        f1: float
            Hight cutoff frequency.
        fs: float
            Sample frequency.
        N : int
            The order of the filter.
        """

        self.f0, self.f1, self.N = f0, f1, N
        self._b, self._a = self._fit(fs)

    # ----------------------------------------------------------------------
    @lru_cache(maxsize=700)
    def _fit(self, fs):
        """Get the numerator and denominator of new sample frequency.

        Parameters
        ----------
        fs : float, optional
            The sampling frequency of the digital system.

        Returns
        -------
        b, a : ndarray, ndarray
            Numerator (`b`) and denominator (`a`) polynomials of the IIR filter.
            Only returned if ``output='ba'``.
        z, p, k : ndarray, ndarray, float
            Zeros, poles, and system gain of the IIR filter transfer
            function.  Only returned if ``output='zpk'``.
        sos : ndarray
            Second-order sections representation of the IIR filter.
            Only returned if ``output=='sos'``.
        """

        if fs != DEFAULT_FS:
            logging.info(f"Compiled `Butter` filter for {fs:0.2f} Hz")
        nyq = fs / 2
        return signal.butter(self.N, (self.f0 / nyq, self.f1 / nyq), 'bandpass')


# ----------------------------------------------------------------------
def compile_filters(FS):
    """Compile filter.

    All filters must be setted for a specified frequnecy sample. Since this
    driver recommend the calculation of sample rate each time the filters must
    be generated before to use them.

    """

    global notch60, band545, band330, band245, band440
    global delta, theta, alpha, beta, band1100, mu
    global impedance, band150, band713, band1550, band550

    notch60 = GenericNotch(f0=60, fs=FS)
    band545 = GenericButterBand(f0=5, f1=45, fs=FS, N=5)
    band330 = GenericButterBand(f0=3, f1=30, fs=FS, N=3)
    band440 = GenericButterBand(f0=4, f1=40, fs=FS, N=3)
    band245 = GenericButterBand(f0=2, f1=45, fs=FS, N=5)
    band1100 = GenericButterBand(f0=1, f1=100, fs=FS, N=5)

    band150 = GenericButterBand(f0=1, f1=50, fs=FS, N=5)
    band713 = GenericButterBand(f0=7, f1=13, fs=FS, N=5)
    band1550 = GenericButterBand(f0=15, f1=50, fs=FS, N=5)
    band550 = GenericButterBand(f0=5, f1=50, fs=FS, N=5)

    delta = GenericButterBand(f0=2, f1=5, fs=FS, N=5)
    theta = GenericButterBand(f0=5, f1=8, fs=FS, N=5)
    alpha = GenericButterBand(f0=8, f1=12, fs=FS, N=5)
    beta = GenericButterBand(f0=13, f1=30, fs=FS, N=5)
    mu = alpha

    f = 1
    impedance = GenericButterBand(f0=31.2 - f, f1=31.2 + f, fs=FS, N=5)


# Precompile filter for 250 Hz
compile_filters(DEFAULT_FS)
logging.info(f"Frequency sample is {DEFAULT_FS} Hz by default.")
