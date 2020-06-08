"""
==========
TCP server
==========

"""

import socket
import logging
import asyncore
from datetime import datetime

# # from openbci_stream.acquisition.binary_stream import BinaryStream


########################################################################
class WiFiShieldTCPServer(asyncore.dispatcher):
    """
    Simple TCP server.
    """

    # ----------------------------------------------------------------------
    def __init__(self, host, binary_stream, kafka_context={}):
        """Example function with types documented in the docstring.

        Parameters
        ----------
        host : str
            Local IP.
        """
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)

        self.set_reuse_addr()
        self.bind((host, 0))
        self.listen(1)
        # self.data = data_queue
        self.kafka_context = kafka_context

        self.binary_stream = binary_stream

    # ----------------------------------------------------------------------
    def handle_accept(self):
        """Redirect the client connection."""
        pair = self.accept()
        if pair is not None:
            sock, addr = pair
            logging.info(f'Incoming connection from {addr}')
            self.handler = asyncore.dispatcher_with_send(sock)
            self.handler.handle_read = self._handle_read
            self.handler.handle_error = self._handle_error

    # ----------------------------------------------------------------------
    def _handle_read(self):
        """Write the input streaming into the Queue object."""
        # self.data.extend(self.handler.recv(33 * 90))

        self.kafka_context.update({'created': datetime.now().timestamp()})
        data = {'context': self.kafka_context,
                'data': self.handler.recv(33 * 90),
                }

        self.binary_stream().stream(data)

    # ----------------------------------------------------------------------
    def _handle_error(self):
        """"""
        # I'm feeling dirty for this "solution"
