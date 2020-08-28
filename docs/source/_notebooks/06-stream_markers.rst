Stream markers with Kafka
=========================

There is two ways to create markers: using the `markers board
mode <_notebooks/05-board_modes.html#marker-mode>`__ and writing
directly on the ``Kafka stream``, this second way is most useful because
the ``producer`` can be running, for example, directly on a stimuli
delivery without the needing for a direct connection with the board.

For example, in ``Python`` is as simple as:

.. code:: ipython3

    from kafka import KafkaProducer
    
    marker_producer = KafkaProducer(bootstrap_servers=['localhost:9092'],
                                    compression_type='gzip',)

The individual markers, are streamed with:

.. code:: ipython3

    marker = 'RIGHT'
    marker_producer.send('marker', marker)

The ``timestamps`` are registered in background.

Read streamed markers
---------------------

.. code:: ipython3

    from openbci_stream.consumer import OpenBCIConsumer
    
    with OpenBCIConsumer() as stream:
        for message in stream:
            if message.topic == 'marker':
                print(message.value)

Redirect markers into the OpenBCI board
---------------------------------------

The package ``Cyton`` use the compatible `board
mode <_notebooks/05-board_modes.html#marker-mode>`__ for create markers,
is possible to redirect the streamed markers from ``Kafka`` to the board
calling ``listen_stream_markers`` after instantiate ``Cyton``.

.. code:: ipython3

    from openbci_stream.acquisition import Cyton
    
    openbci = Cyton('serial', capture_stream=True)
    
    openbci.listen_stream_markers(host='localhost:9092')
    openbci.stream(15)
    
    print(openbci.eeg_time_series)
