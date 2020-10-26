#!/usr/bin/bash

pacman -S hostapd dnsmasq
systemctl enable hostapd dnsmasq dhcpcd
systemctl start hostapd dnsmasq dhcpcd

cp /etc/dhcpcd.conf /etc/dhcpcd.conf.orig
echo "
interface wlan0
static ip_address=192.168.1.1/24
" >> /etc/dhcpcd.conf

cp /etc/dnsmasq.conf /etc/dnsmasq.conf.orig
echo "
port=5353
interface=wlan0
dhcp-range=192.168.1.100,192.168.1.200,24h
dhcp-option=option:dns-server,192.168.1.1
" >> /etc/dnsmasq.conf

echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' >> /etc/default/hostapd

mv /etc/hostapd/hostapd.conf /etc/hostapd/hostapd.orig
echo "
interface=wlan0
driver=nl80211
ssid=OpenBCI-Stream
hw_mode=g
channel=6
ieee80211n=1
wmm_enabled=1
ht_capab=[HT40][SHORT-GI-20][DSSS_CCK-40]
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_key_mgmt=WPA-PSK
wpa_passphrase=raspberrypi
rsn_pairwise=CCMP
" >> /etc/hostapd/hostapd.conf

echo "net.ipv4.ip_forward=1 " >> /etc/sysctl.conf

echo "Created an access point with SSID: 'OpenBCI-Stream' and password 'raspberrypi'"