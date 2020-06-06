"""
============
EEG Features
============

"""

import numpy as np
from scipy.fftpack import fft, fftfreq, fftshift
from scipy.signal import welch as sci_welch
from datetime import datetime


# ----------------------------------------------------------------------
def entropy(eeg):
    """Signal entropy."""

    upper = np.mean(eeg, axis=1) + 3 * np.std(eeg, axis=1)
    lower = np.mean(eeg, axis=1) - 3 * np.std(eeg, axis=1)

    bins = np.linspace(lower, upper, 20, axis=1)

    counts = [np.histogram(*xbin)[0] for xbin in zip(eeg, bins)]

    p = counts / np.sum(counts, axis=1)[:, None]
    p = [np.compress(p_ != 0, p_) for p_ in p]  # remove zeros

    H = np.array([-np.sum(p_ * np.log(p_)) / len(p_) for p_ in p])
    return H


# ----------------------------------------------------------------------
# def energy(eeg, / , axis=-1):
def energy(eeg, axis=-1):
    """Signal energy."""

    E = np.sum(abs(eeg ** 2), axis=axis)
    return E


# ----------------------------------------------------------------------
# def std(eeg, / , axis=-1):
def std(eeg, axis=-1):
    """Standard deviation."""

    STD = np.std(eeg, axis=axis)
    return STD


# ----------------------------------------------------------------------
# def spectrum(eeg, /, d=None, fs=None, timestamp=None, axis=-1):
def spectrum(eeg, d=None, fs=None, timestamp=None, axis=-1):
    """Spectral power density using Fourier."""

    timestamp = np.array(timestamp)

    if timestamp.any():
        if isinstance(timestamp[-1], (int, float)):
            delta = datetime.fromtimestamp(timestamp[-1]) - datetime.fromtimestamp(timestamp[0])
        else:
            delta = timestamp[-1] - timestamp[0]
        fs = max(eeg.shape) / delta.total_seconds()

    if fs:
        d = 1 / fs

    if axis is None:
        if eeg.shape[0] > eeg.shape[1]:
            axis = 0
        else:
            axis = 1

    Yf = fftshift(np.abs(fft(eeg, axis=axis)))
    f = fftshift(fftfreq(Yf.shape[1], d))

    n = (Yf.shape[1] // 2)
    Yf = Yf[:, n:] * (2 / Yf.shape[1])
    f = f[n:]

    return f, Yf


# ----------------------------------------------------------------------
# def welch(eeg, /, d=None, fs=None, timestamp=None, axis=-1):
def welch(eeg, d=None, fs=None, timestamp=None, axis=-1):
    """Spectral power density using Welch's method."""

    timestamp = np.array(timestamp)

    if timestamp.any():
        if isinstance(timestamp[-1], (int, float)):
            delta = datetime.fromtimestamp(timestamp[-1]) - datetime.fromtimestamp(timestamp[0])
        else:
            delta = timestamp[-1] - timestamp[0]
        fs = max(eeg.shape) / delta.total_seconds()

    if fs:
        d = 1 / fs

    if axis is None:
        if eeg.shape[0] > eeg.shape[1]:
            axis = 0
        else:
            axis = 1

    f, p = sci_welch(eeg, 1 / d, window='flattop', nperseg=min(eeg.shape[1], 1024), scaling='spectrum', axis=axis)
    return f, p


