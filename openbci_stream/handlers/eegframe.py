from openbci_stream.preprocess import eeg_filters
from openbci_stream.preprocess import eeg_features
import logging
import inspect

import numpy as np


########################################################################
class EEGFrame:
    """"""

    # ----------------------------------------------------------------------
    def __init__(self, openbci):
        """Constructor"""

        if not(openbci.eeg_buffer.qsize() or openbci.eeg_pack.qsize()):
            logging.warning("Not enough data to creating `EEGFrame` object, EEG data must collected before.")
            return

        if openbci.eeg_buffer.qsize():
            self.data = np.array(openbci.eeg_buffer.queue)
            self.sample, self.eeg, self.aux, self.footer, self.timestamp = self.data.T

        elif openbci.eeg_pack.qsize():
            self.data = np.array(openbci.eeg_pack.queue)

        self.default_kwargs = {
            'sample': self.sample,
            # 'eeg': self.eeg,
            'aux': self.aux,
            'footer': self.footer,
            'timestamp': self.timestamp,
        }

    # ----------------------------------------------------------------------
    def __getattr__(self, attr):
        """"""
        if hasattr(eeg_filters, attr):
            _kwargs = {key: self.default_kwargs[key] for key in self.default_kwargs if key in inspect.getargspec(getattr(eeg_features, attr)).args}
            return lambda **kwargs: getattr(eeg_filters, attr)(np.stack(self.eeg), **{**_kwargs, **kwargs})

        elif hasattr(eeg_features, attr):
            _kwargs = {key: self.default_kwargs[key] for key in self.default_kwargs if key in inspect.getargspec(getattr(eeg_features, attr)).args}
            return lambda **kwargs: getattr(eeg_features, attr)(np.stack(self.eeg), **{**_kwargs, **kwargs})





