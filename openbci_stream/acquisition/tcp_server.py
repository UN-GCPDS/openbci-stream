"""
==========
TCP server
==========

The module WiFi for OpenBCI receive the instructions to connect with a TCP
server, before that happens, the server must be running and waiting for clients.

"""

import socket
import logging
import asyncore
from datetime import datetime
from typing import Dict, Any, Callable


########################################################################
class WiFiShieldTCPServer(asyncore.dispatcher):
    """Create a TCP server that handles the connexión of the WiFi module.

    Parameters
    ----------
    host
        IP address of the machine that WiFi module will connect.
    binary_stream
        Function that return a kafka producer, this producer could not exist in
        the very moment of creation of this class instance.
    context
        Information from the acquisition side useful for deserializing and that
        will be packaged back in the stream.
    """

    # ----------------------------------------------------------------------
    def __init__(self, host, binary_stream: Callable, kafka_context: Dict[str, Any] = {}) -> None:
        """"""
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)

        self.set_reuse_addr()
        self.bind((host, 0))
        self.listen(1)
        # self.data = data_queue
        self.kafka_context = kafka_context

        self.binary_stream = binary_stream
        self._gain = None

    # ----------------------------------------------------------------------
    def handle_accept(self) -> None:
        """Redirect the client connection."""
        pair = self.accept()
        if pair is not None:
            sock, addr = pair
            logging.info(f'Incoming connection from {addr}')
            self.handler = asyncore.dispatcher_with_send(sock)
            self.handler.handle_read = self._handle_read
            self.handler.handle_error = self._handle_error

    # ----------------------------------------------------------------------
    def set_gain(self, gain) -> None:
        """"""
        self._gain = gain

    # ----------------------------------------------------------------------
    def _handle_read(self) -> None:
        """Write the input streaming into the binary stream.

        There is a maximum of 3000 bytes that can read at once, so it is set to
        2970, a 33 multiple. But this not means that read this amount of data
        on all events, the module WiFi will send on their consideration.
        """

        self.kafka_context.update({'created': datetime.now().timestamp()})

        if self._gain:
            self.kafka_context.update({'gain': self._gain})
        else:
            if self.kafka_context['daisy']:
                self.kafka_context.update({'gain': [24] * 16})
            else:
                self.kafka_context.update({'gain': [24] * 8})

        data = {'context': self.kafka_context,
                'data': self.handler.recv(33 * 90),
                }

        self.binary_stream().stream(data)

    # ----------------------------------------------------------------------
    def _handle_error(self) -> None:
        """"""
        # I'm feeling dirty for this "solution"
