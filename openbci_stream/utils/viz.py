from scipy.signal import welch
from matplotlib.lines import Line2D
from matplotlib import pyplot as plt
import numpy as np


# ----------------------------------------------------------------------
def fft_3d(signal, fmax, fs, ds, hs, channels, nperseg=2**13, ax=None):
    """"""
    f, _ = welch(signal[0], fs=fs, nperseg=nperseg)
    x = np.argmin(abs(f - fmax))

    if ax is None:
        plt.figure(figsize=(20, 8), dpi=90)
        ax = plt.axes(frameon=False)

    for i, eeg_ in enumerate(signal):
        f, Pxx = welch(eeg_, fs=fs, nperseg=nperseg)

        f = f[:x]
        Pxx = Pxx[:x]

        ax.fill_betweenx(Pxx + (i * hs), (i * ds), f + (i * ds), alpha=0.8,
                         color='w', edgecolor="w", linewidth=1, zorder=eeg_.shape[0] - i)
        ax.plot(f + (i * ds), Pxx + (i * hs), alpha=0.8,
                color='k', linewidth=1, zorder=eeg_.shape[0] - i)

        plt.text(fmax * 1.01 + (i * ds), (i * hs), channels[i])

    xticks = np.arange(0, f[-1] + 1, f[-1] // 10)
    ticklabels = map(str, xticks)
    plt.xticks(xticks, ticklabels)

    ax.axes.xaxis.get_ticklabels()
    ax.axes.yaxis.set_ticklabels([])
    ax.set_frame_on(False)
    ax.get_xaxis().tick_bottom()
    ax.axes.get_yaxis().set_visible(False)

    xmin, xmax = ax.get_xaxis().get_view_interval()
    ymin, ymax = ax.get_yaxis().get_view_interval()
    ax.add_artist(Line2D((xmin, f[-1] + 10),
                         (ymin, ymin), color='black', linewidth=2))

    for g in np.arange(50, f[-1], 50):
        plt.plot([g, g + ds * signal.shape[0]], [0, hs * signal.shape[0]],
                 linestyle=(0, (5, 10)), zorder=0, color='k', alpha=0.2, linewidth=0.5)

    plt.xlabel('Frequency (Hz)')

