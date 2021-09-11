#!/usr/bin/bash

echo "Installing things"
sudo pacman -S --needed git base-devel
cd

#git clone https://github.com/UN-GCPDS/archlinux-PKGBUILD.git
#cd archlinux-PKGBUILD

#echo "Installing Zookeeper"
#cd zookeeper
#makepkg -si

#echo "Installing Kafka"
#cd ../kafka
#makepkg -si

#cd
#sudo rm -r archlinux-PKGBUILD

echo "Installing Yay"
cd
sudo pacman -S --needed git base-devel
git clone https://aur.archlinux.org/yay.git
cd yay
makepkg -si
cd
sudo rm -r yay

echo "Installing Kafka"
yay -S kafka
