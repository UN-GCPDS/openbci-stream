#!/usr/bin/bash

sudo pacman -S --needed python python-pip gcc cython hdf5
sudo pip install -U openbci-stream systemd_service
stream_install_kafka.sh
sudo stream_configure_kafka.sh
sudo stream_configure_ntpd.sh
sudo stream_access_point.sh
sudo stream_eeg systemd
sudo stream_rpyc systemd
sudo stream_bin2eeg systemd
sudo systemctl daemon-reload
sudo systemctl enable stream_eeg stream_rpyc stream_bin2eeg0 stream_bin2eeg1 stream_bin2eeg2 stream_bin2eeg3
sudo systemctl start stream_eeg stream_rpyc stream_bin2eeg0 stream_bin2eeg1 stream_bin2eeg2 stream_bin2eeg3
