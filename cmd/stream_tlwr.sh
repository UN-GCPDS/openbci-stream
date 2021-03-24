#!/usr/bin/bash

pacman -S python python-pip gcc cython hdf5
pip install openbci-stream
stream_install_kafka.sh
stream_configure_kafka.sh
stream_access_point.sh
stream_configure_ntpd.sh
stream_eeg systemd
stream_rpyc systemd
systemctl enable stream_eeg stream_rpyc
systemctl start stream_eeg stream_rpyc
