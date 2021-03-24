#!/usr/bin/bash

function secure_file {
    if test -f $1.orig; then
        rm $1
        cp $1.orig $1
    else
        cp $1 $1.orig
    fi
}

echo "Installing Yay"
cd
pacman -S --needed git base-devel
git clone https://aur.archlinux.org/yay.git
cd yay
makepkg -si
cd
rm -r yay

echo "Installing Kafka"
yay -S kafka




