#!/usr/bin/bash

echo "Installing things"
sudo pacman -S --needed git base-devel
cd

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
