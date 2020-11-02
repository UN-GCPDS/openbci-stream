# OpenBCI-Stream 
High level Python module for EEG/EMG/ECG acquisition and distributed streaming for OpenBCI Cyton board.

![GitHub top language](https://img.shields.io/github/languages/top/un-gcpds/openbci-stream)
![PyPI - License](https://img.shields.io/pypi/l/openbci-stream)
![PyPI](https://img.shields.io/pypi/v/openbci-stream)
![PyPI - Status](https://img.shields.io/pypi/status/openbci-stream)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/openbci-stream)
![GitHub last commit](https://img.shields.io/github/last-commit/un-gcpds/openbci-stream)
![CodeFactor Grade](https://img.shields.io/codefactor/grade/github/UN-GCPDS/openbci-stream)


Consist in a set of scripts which deals with the configuration and connection with the board, is compatible with both connection modes supported by [Cyton](https://shop.openbci.com/products/cyton-biosensing-board-8-channel?variant=38958638542): RFduino (Serial dongle) and WiFi (with the OpenBCI WiFi Shield). These drivers are a stand-alone library that can be used to handle the board from three different endpoints: (i) a [Command Line Interface](06-command_line_interface.ipynb) (CLI) with simple instructions configure, start and stop data acquisition, debug stream status and register events markers; (ii) a [Python Module](03-data_acuisition.ipynb) with high-level instructions and asynchronous acquisition; (iii) an object-proxying using Remote Python Call (RPyC) for [distributed implementations](A4-server-based-acquisition.ipynb) that can manipulate the Python modules as if they were local, this last mode needs a daemon running in the remote host that will be listening connections and driving instructions.

The main functionality of the drivers reside on to serve a real-time and distributed access to data flow, even on single machine implementations, this is achieved by the implementation of [Kafka](https://kafka.apache.org/) and their capabilities to create multiple topics for classifying the streaming, these topics are used to separate the neurophysiological data from the [event markers](05-stream_markers), so the clients can subscript to a specific topic for injecting or read content, this means that is possible to implement an event register in a separate process that stream markers for all clients in real-time without handle dense time-series data. A crucial issue stays on [time synchronization](A4-server-based_acquisition.ipynb#Step-5---Configure-time-server), is required that all system components in the network be referenced to the same local real-time protocol (RTP) server.

## Main features

  * **Asynchronous acquisition:** Acquisition and deserialization is done in uninterrupted parallel processes, in this way the sampling rate keeps stable as long as possible.
  * **Distributed streaming system:** The acquisition, processing, visualizations  and any other system that needs to be feeded with EEG/EMG/ECG real-time data can be run with their own architecture.
  * **Remote board handle:** Same code syntax for develop and debug Cython boards connected in any node in the distributed system.
  * **Command line interface:** A simple interface for handle the start, stop and access to data stream directly from the command line.
  * **Markers/Events handler:** Beside the _marker boardmode_ available in Cyton, a stream channel for the reading and writing of markers are available for use it in any development.
