OpenBCI-Stream
==============

Hight level Python module for handle OpenBCI hardware and stream data.

.. warning::

   -  This is NOT an official package from `OpenBCI
      team <https://openbci.com/>`__.
   -  This module is still unstable and not recommended for use in
      production.

What is?
--------

A Python module for develop hight performance interfaces with `OpenBCI
boards <https://openbci.com/>`__. Currently, we have support for
Cyton+Daisy and their WiFi module, additionally, we provide a real time
data stream with `Kafka <https://kafka.apache.org/>`__. All source code
can be accessed from our `bitbucket
repository <https://bitbucket.org/gcpds/python-openbci_stream/>`__.

What do we want?
----------------

We want a stable, high level, easy to use and extensible Python module
focused on the awesome hardware provided by OpenBCI that can be used for
students and researchers, we are developing too a set of tools for
preprocessing, real-time data handling and streaming of EEG signals.

Who are we?
-----------

We are a research group concentrated on digital processing of signals
and machine learning from the National University of Colombia at
Manizales
(`GCPDS <http://www.hermes.unal.edu.co/pages/Consultas/Grupo.xhtml;jsessionid=8701CFAD84FB5D540090846EA8912D48.tomcat6?idGrupo=615&opcion=1%3E>`__).

Examples
--------

EEG acquisition from Serial

.. code:: ipython3

    import time
    from openbci_stream.acquisition import CytonRFDuino
    
    openbci = CytonRFDuino(capture_stream=True, daisy=False)
    openbci.start_stream()
    time.sleep(5)
    openbci.stop_stream()
    
    print(openbci.eeg_time_series.shape)


.. parsed-literal::

    WARNING:root:Stream must be stoped for read the current boardmode
    WARNING:kafka.coordinator.consumer:group_id is None: disabling auto-commit.


.. parsed-literal::

    (8, 1018)


Stream markers

.. code:: ipython3

    import time
    from datetime import datetime
    import pickle
    from kafka import KafkaProducer
    
    producer_eeg = KafkaProducer(bootstrap_servers=['localhost:9092'],
                                 value_serializer=lambda x: pickle.dumps(x))
    
    def stream_marker(marker):
        producer_eeg.send('marker', {'timestamp': datetime.now().timestamp(), 
                                     'marker': marker})
    
    stream_marker('RIGHT')
    time.sleep(1) 
    stream_marker('LEFT')
    time.sleep(1) 
    stream_marker('RIGHT')
    time.sleep(1) 
    stream_marker('LEFT')    

Saving EEG data from command line

.. code:: ipython3

    $ python openbci_cli.py serial  --start  --output 'eeg_out.csv'
    Writing data in 
    Ctrl+C for stop it.
    
    [EEG] 2020-03-04 22:57:57.117478        0.0146s ago     254 samples, 8 channels
    [EEG] 2020-03-04 22:57:58.138276        0.0153s ago     254 samples, 8 channels
    [EEG] 2020-03-04 22:57:59.158153        0.0161s ago     302 samples, 8 channels
    [EEG] 2020-03-04 22:58:00.179612        0.0155s ago     254 samples, 8 channels
    [EEG] 2020-03-04 22:58:01.199204        0.0164s ago     254 samples, 8 channels
    [EEG] 2020-03-04 22:58:02.219734        0.0154s ago     254 samples, 8 channels
    [EEG] 2020-03-04 22:58:03.239956        0.0159s ago     254 samples, 8 channels
    [EEG] 2020-03-04 22:58:04.259876        0.0134s ago     254 samples, 8 channels
    [EEG] 2020-03-04 22:58:05.281410        0.0170s ago     256 samples, 8 channels
    [EEG] 2020-03-04 22:58:06.301453        0.0199s ago     256 samples, 8 channels
    [EEG] 2020-03-04 22:58:07.322150        0.0141s ago     254 samples, 8 channels
