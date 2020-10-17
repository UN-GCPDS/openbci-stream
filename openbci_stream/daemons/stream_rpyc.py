"""
============
OpenBCI-RPyC
============

OpenBCI-RPyC (Remote Python Call) is the waty to handle OpenBCI boards
attached remotely.
"""

import rpyc
from openbci_stream.acquisition import CytonRFDuino, CytonWiFi


########################################################################
class StremamService(rpyc.Service):
    """Server with RPyC for control OpenBCI board remotely.
    """

    # ----------------------------------------------------------------------
    def exposed_CytonRFDuino(self, *args, **kwargs):
        return CytonRFDuino(*args, **kwargs)

    # ----------------------------------------------------------------------
    def exposed_CytonWiFi(self, *args, **kwargs):
        """"""
        return CytonWiFi(*args, **kwargs)

    # #----------------------------------------------------------------------
    # def on_connect(self, conn):
        # """code that runs when a connection is created.
        # """
        # pass

    # #----------------------------------------------------------------------
    # def on_disconnect(self, conn):
        # """code that runs after the connection has already closed.
        # """
        # pass

# ----------------------------------------------------------------------


def start_service():
    """Start the rpyc server.
    """
    from rpyc.utils.server import ThreadedServer

    t = ThreadedServer(StremamService,
                       port=18861,
                       protocol_config={
                           'allow_public_attrs': True,
                       }
                       )
    t.start()


if __name__ == "__main__":
    start_service()
