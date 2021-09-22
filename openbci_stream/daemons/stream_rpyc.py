"""
=======================
Distributed acquisition
=======================

RPyC (Remote Python Call) is the way to handle OpenBCI boards attached remotely.

For examples and descriptions refers to documentation:
`Data Acquisition - Distributed acquisition <../03-data_acquisition.ipynb/#Distributed-acquisition>`_
"""

import sys
import logging
import requests
import rpyc
from openbci_stream.acquisition import CytonRFDuino, CytonWiFi, Cyton

from openbci_stream.utils import autokill_process
autokill_process(name='stream_rpyc')


DEBUG = ('--debug' in sys.argv)

if DEBUG:
    logging.getLogger().setLevel(logging.DEBUG)
    # logging.getLogger('kafka').setLevel(logging.WARNING)


########################################################################
class RequestWifi:
    """"""

    # ----------------------------------------------------------------------
    def status(self, ip):
        """Constructor"""
        response = requests.get(f'http://{ip}/board', timeout=0.3)
        if response.json()['board_connected']:
            return response.json()
        else:
            return False


########################################################################
class StremamService(rpyc.Service):
    """Server with RPyC for control OpenBCI board remotely."""
    last_service = None

    # ----------------------------------------------------------------------
    def exposed_CytonRFDuino(self, *args, **kwargs):
        """"""
        if StremamService.last_service:
            if not StremamService.last_service.closed:
                StremamService.last_service.is_recycled = True
                return StremamService.last_service

        StremamService.last_service = CytonRFDuino(*args, **kwargs)
        StremamService.last_service.is_recycled = False
        return StremamService.last_service

    # ----------------------------------------------------------------------
    def exposed_CytonWiFi(self, *args, **kwargs):
        """"""
        if StremamService.last_service:
            if not StremamService.last_service.closed:
                StremamService.last_service.is_recycled = True
                return StremamService.last_service

        StremamService.last_service = CytonWiFi(*args, **kwargs)
        StremamService.last_service.is_recycled = False
        return StremamService.last_service

    # ----------------------------------------------------------------------
    def exposed_Cyton(self, *args, **kwargs):
        """"""
        if StremamService.last_service:
            if not StremamService.last_service.closed:
                StremamService.last_service.is_recycled = True
                return StremamService.last_service

        StremamService.last_service = Cyton(*args, **kwargs)
        StremamService.last_service.is_recycled = False
        return StremamService.last_service

    # ----------------------------------------------------------------------
    def exposed_Wifi(self, ip):
        """"""
        req = RequestWifi()
        return req.status(ip)


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
