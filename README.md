> Developed by [Yeison Nolberto Cardona Álvarez](https://github.com/yeisonCardona)  
> [Andrés Marino Álvarez Meza, PhD.](https://github.com/amalvarezme)  
> César Germán Castellanos Dominguez, PhD.  
> _Digital Signal Processing and Control Group_  | _Grupo de Control y Procesamiento Digital de Señales ([GCPDS](https://github.com/UN-GCPDS/))_  
> _National University of Colombia at Manizales_ | _Universidad Nacional de Colombia sede Manizales_

----

# OpenBCI-Stream 
High level Python module for EEG/EMG/ECG acquisition and distributed streaming for OpenBCI Cyton board.

![GitHub top language](https://img.shields.io/github/languages/top/un-gcpds/openbci-stream?)
![PyPI - License](https://img.shields.io/pypi/l/openbci-stream?)
![PyPI](https://img.shields.io/pypi/v/openbci-stream?)
![PyPI - Status](https://img.shields.io/pypi/status/openbci-stream?)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/openbci-stream?)
![GitHub last commit](https://img.shields.io/github/last-commit/un-gcpds/openbci-stream?)
![CodeFactor Grade](https://img.shields.io/codefactor/grade/github/UN-GCPDS/openbci-stream?)
[![Documentation Status](https://readthedocs.org/projects/openbci-stream/badge/?version=latest)](https://openbci-stream.readthedocs.io/en/latest/?badge=latest)

Comprise a set of scripts that deals with the configuration and connection with the board, also is compatible with both connection modes supported by [Cyton](https://shop.openbci.com/products/cyton-biosensing-board-8-channel?variant=38958638542): RFduino (Serial dongle) and Wi-Fi (with the OpenBCI Wi-Fi Shield). These drivers are a stand-alone library that can handle the board from three different endpoints: (i) a [Command-Line Interface](06-command_line_interface.ipynb) (CLI) with simple instructions configure, start and stop data acquisition, debug stream status, and register events markers; (ii) a [Python Module](03-data_acuisition.ipynb) with high-level instructions and asynchronous acquisition; (iii) an object-proxying using Remote Python Call (RPyC) for [distributed implementations](A4-server-based-acquisition.ipynb) that can manipulate the Python modules as if they were local, this last mode needs a daemon running in the remote host that will listen to connections and driving instructions.

The main functionality of the drivers live on to serve real-time and distributed access to data flow, even on single machine implementations, this is achieved by implementing [Kafka](https://kafka.apache.org/) and their capabilities to create multiple topics for classifying the streaming, these topics are used to separate the neurophysiological data from the [event markers](05-stream_markers), so the clients can subscribe to a specific topic for injecting or read content, this means that is possible to implement an event register in a separate process that stream markers for all clients in real-time without handle dense time-series data. A crucial issue that stays on [time synchronization](A4-server-based_acquisition.ipynb#Step-5---Configure-time-server), all systems components in the network should have the same real-time protocol (RTP) server reference. 

## Main features

  * **Asynchronous acquisition:** Acquisition and deserialization are done in uninterrupted parallel processes. In this way, the sampling rate keeps stable as long as possible.
  * **Distributed streaming system:** The acquisition, processing, visualizations, and any other system that needs to be fed with EEG/EMG/ECG real-time data can run with their architecture.
  * **Remote board handle:** Same code syntax for developing and debug Cython boards connected to any node in the distributed system.
  * **Command-line interface:** A simple interface for handle the start, stop, and access to data stream directly from the command line.
  * **Markers/Events handler:** Besides the marker boardmode available in Cyton, a stream channel for the reading and writing of markers is available for use in any development. 
  * **Multiple boards:** Is possible to use multiple OpenBCI boards just by adding multiple endpoints to the commands.

## Examples


```python
# Acquisition with blocking call

from openbci_stream.acquisition import Cyton
openbci = Cyton('serial', endpoint='/dev/ttyUSB0', capture_stream=True)

# blocking call
openbci.stream(15)  # collect data for 15 seconds

# openbci.eeg_time_series 
# openbci.aux_time_series
# openbci.timestamp_time_series 
```


```python
# Acquisition with asynchronous call

from openbci_stream.acquisition import Cyton
openbci = Cyton('wifi', endpoint='192.68.1.113', capture_stream=True)
openbci.stream(15) # collect data for 15 seconds

# asynchronous call
openbci.start_stream()
time.sleep(15)  # collect data for 15 seconds
openbci.stop_stream()
```


```python
# Remote acquisition

from openbci_stream.acquisition import Cyton
openbci = Cyton('serial', endpoint='/dev/ttyUSB0', host='192.168.1.1', capture_stream=True)

# blocking call
openbci.stream(15)  # collect data for 15 seconds
```


```python
# Consumer for active streamming

from openbci_stream.acquisition import OpenBCIConsumer
with OpenBCIConsumer() as stream:
    for i, message in enumerate(stream):
        if message.topic == 'eeg':
            print(f"received {message.value['samples']} samples")
            if i == 9:
                break
```


```python
# Create stream then consume data

from openbci_stream.acquisition import OpenBCIConsumer
with OpenBCIConsumer(mode='serial', endpoint='/dev/ttyUSB0', streaming_package_size=250) as (stream, openbci):
    t0 = time.time()
    for i, message in enumerate(stream):
        if message.topic == 'eeg':
            print(f"{i}: received {message.value['samples']} samples")
            t0 = time.time()
            if i == 9:
                break
```


```python
# Acquisition with multiple boards

from openbci_stream.acquisition import Cyton
openbci = Cyton('wifi', endpoint=['192.68.1.113', '192.68.1.185'], capture_stream=True)
openbci.stream(15) # collect data for 15 seconds

# asynchronous call
openbci.start_stream()
time.sleep(15)  # collect data for 15 seconds
openbci.stop_stream()
```
