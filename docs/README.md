# OpenBCI-Stream 
High level Python module for EEG acquisition and streaming for OpenBCI Cyton board.

## About this project

### What is it?
A Python module for high-performance interfaces development with [OpenBCI boards](https://openbci.com/).
Currently, we have support for Cyton+Daisy and their WiFi module, additionally, we provide a real-time data streaming feature using [Kafka](https://kafka.apache.org/).

### What we want?
We want a stable, high level, easy to use and extensible Python module focalizes on the hardware provided by OpenBCI, a library that can be used for students, hobbyist and researchers, we are developing a set of tools for preprocessing, real-time data handling and streaming of EEG signals.

### About us?
We are a research group focused on digital processing of signals and machine learning from the National University of Colombia at Manizales ([GCPDS](http://www.hermes.unal.edu.co/pages/Consultas/Grupo.xhtml;jsessionid=8701CFAD84FB5D540090846EA8912D48.tomcat6?idGrupo=615&opcion=1>)).

## Main features

  * **Asynchronous acquisition:** After the board initialization, the data acquisition can be executed asynchronously, this feature ables to realize background operations without interrupt and affect the data sampling [read more...](../html/_notebooks/04-data_acquisition.html#initialize-stream)
  * **Streaming data:** The EEG data is streamed with [Apache Kafka](https://kafka.apache.org/), this means that the data can be consumed from any other interface or language [read more...](../html/_notebooks/04-data_acquisition.html#access-to-stream)
  * **Remote host:** Is possible to get OpenBCI running in one computing system and manage it from other [read more...](../html/_notebooks/A4-configure_remote_host.html)
  * **Command line interface:** A simple interface is available for handle the start, stop and access to data stream directly from the command line [read more...](../html/_notebooks/A3-command_line_interface.html)
  * **Markers/Events handler:**  [read more...](../html/_notebooks/07-stream_markers.html)
  * **Distributed platforms: **

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
