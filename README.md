# OpenBCI-Stream 
High level Python module for handle OpenBCI hardware and stream data.

<div class="alert alert-block alert-warning">
    <ul>
        <li>This is NOT an official package from <a href='https://openbci.com/'>OpenBCI team</a>.</li>
        <li>This module is still unstable and not recommended for use in production.</li>
    </ul>
</div>

# About project

## What is?
A Python module for high-performance interfaces development with [OpenBCI boards](https://openbci.com/).
Currently, we have support for Cyton+Daisy and their WiFi module, additionally, we provide a real-time data streaming feature using [Kafka](https://kafka.apache.org/).

## What do we want?
We want a stable, high level, easy to use and extensible Python module focalize on the hardware provided by OpenBCI, a library that can be used for students, hobbyist and researchers, we are developing a set of tools for preprocessing, real-time data handling and streaming of EEG signals.

## Who are we?
We are a research group focused on digital processing of signals and machine learning from the National University of Colombia at Manizales ([GCPDS](http://www.hermes.unal.edu.co/pages/Consultas/Grupo.xhtml;jsessionid=8701CFAD84FB5D540090846EA8912D48.tomcat6?idGrupo=615&opcion=1>)).

## Examples

Read 5 seconds EEG from serial:


```python
from openbci_stream.acquisition import CytonRFDuino
import time

openbci = CytonRFDuino(capture_stream=True, daisy=False)
openbci.start_stream()
time.sleep(5)
openbci.stop_stream()

print(openbci.eeg_time_series.shape)
```

Stream markers through Kafka


```python
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
```

Starting streaming from command line and store as 'CSV'


```python
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
```
