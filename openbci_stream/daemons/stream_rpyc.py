"""
=======================
Distributed acquisition
=======================

RPyC (Remote Python Call) is the way to handle OpenBCI boards attached remotely.

For examples and descriptions refers to documentation:
`Data Acquisition - Distributed acquisition <../03-data_acquisition.ipynb/#Distributed-acquisition>`_
"""

import rpyc
from openbci_stream.acquisition import CytonRFDuino, CytonWiFi


########################################################################
class StremamService(rpyc.Service):
    """Server with RPyC for control OpenBCI board remotely."""

    # ----------------------------------------------------------------------
    def exposed_CytonRFDuino(self, *args, **kwargs):
        return CytonRFDuino(*args, **kwargs)

    # ----------------------------------------------------------------------
    def exposed_CytonWiFi(self, *args, **kwargs):
        """"""
        return CytonWiFi(*args, **kwargs)


# ----------------------------------------------------------------------
def start_service() -> None:
    """Start the rpyc server."""
    from rpyc.utils.server import ThreadedServer

    t = ThreadedServer(StremamService,
                       port=18861,
                       protocol_config={
                           'allow_public_attrs': True,
                           'allow_pickle': True,
                       }
                       )
    t.start()


if __name__ == "__main__":
    start_service()
