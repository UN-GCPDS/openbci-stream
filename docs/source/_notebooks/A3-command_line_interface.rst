Appendix 3 - Command line interface
===================================


.. code:: ipython3

    from openbci_stream.utils import openbci_cli
    openbci_cli.parser.print_usage()


.. parsed-literal::

    usage: openbci_cli [-h] {serial,wifi,stream,marker} ...


Interface
---------

There are 4 options for interface: ``serial``, ``wifi``, ``stream`` and
``marker``

``serial`` and ``wifi``
~~~~~~~~~~~~~~~~~~~~~~~

| With this option we can ``--star`` and ``--stop`` the data streaming,
  we can too send a ``--command`` based on the
  `SDK <https://docs.openbci.com/docs/02Cyton/CytonSDK>`__
  documentation.
| The difference between ``serial`` and ``wifi`` are the options
  ``--port`` and ``--ip`` respectively, the first is used to select the
  serial port and the second is used for select the IP of the WiFi
  module.

.. code:: ipython3

    # $ openbci_cli serial -h
    openbci_cli.parser.parse_args(['serial', '-h'])


.. parsed-literal::

    usage: openbci_cli serial [-h] [--start | --stop] [-c COMMAND [COMMAND ...]]
                              [--stream_samples STREAM_SAMPLES] [--daisy]
                              [--host HOST] [--output OUTPUT]
                              [--output_markers OUTPUT_MARKERS] [--port PORT]
    
    optional arguments:
      -h, --help            show this help message and exit
      --start               Start stream
      --stop                Stop stream
      -c COMMAND [COMMAND ...], --command COMMAND [COMMAND ...]
                            Send commands after connection established
      --stream_samples STREAM_SAMPLES
                            Number of samples to receive in stream
      --daisy               Enable or disable daisy
      --host HOST           Hostname where is running the acquisition system
      --output OUTPUT       Write stream into file
      --output_markers OUTPUT_MARKERS
                            Write markers into file
      --port PORT           Serial port


::


    An exception has occurred, use %tb to see the full traceback.


    SystemExit: 0



For example if we wan to start a stream from serial device in port
``/dev/ttyUSB0`` with daisy module attached, streaming 250 samples per
second:

.. code:: ipython3

    openbci_cli serial --port /dev/ttyUSB0 --daisy --stream_samples 250 --start

or start a stream from wifi device in IP ``192.168.1.113`` in marker
mode without daisy module, streaming 2000 samples per second:

.. code:: ipython3

    openbci_cli wifi --ip 192.168.1.113 --stream_samples 2000 -c ~3 --start

the option ``~3`` according to the
`SDK <https://docs.openbci.com/docs/02Cyton/CytonSDK#sample-rate>`__ is
for configure the sample rate in 2000 samples per second,
``SAMPLE_RATE_2KSPS`` is valid too:

.. code:: ipython3

    openbci_cli wifi --ip 192.168.1.113 --stream_samples 2000 -c SAMPLE_RATE_2KSPS --start

``stream``
~~~~~~~~~~

With this option we access to some stream that already started

.. code:: ipython3

    openbci_cli stream

``marker``
~~~~~~~~~~

With this option we enter in a interactive console for create marker.

.. code:: ipython3

    openbci_cli marker

Output
------

For the interfaces ``serial`` and ``wifi``, when ``--start`` a new
stream, and for ``stream`` interfaces there is an option ``--output``
for storage the stream into HDF5 format.

.. code:: ipython3

    openbci_cli serial --port /dev/ttyUSB0 --daisy --output 'saved_data.h5' --stream_samples 250 --start

Remote host
-----------

All interfaces and commands here explained can be executed from a
`remote host <A4-configure_remote_host>`__ with the option ``--host``,
this mean that we can control the acquisition system from a device
connected in the same network.
