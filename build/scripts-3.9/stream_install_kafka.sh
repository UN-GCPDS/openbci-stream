#!/usr/bin/bash

echo "Installing things"
sudo pacman -S --needed git base-devel
cd

git clone https://github.com/UN-GCPDS/archlinux-PKGBUILD.git
cd archlinux-PKGBUILD

echo "Installing Zookeeper"
cd zookeeper
makepkg -si

echo "Installing Kafka"
cd ../kafka
makepkg -si

cd
sudo rm -r archlinux-PKGBUILD
