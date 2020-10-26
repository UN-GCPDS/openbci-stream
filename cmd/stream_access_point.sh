#!/usr/bin/bash

pacman -S hostapd dnsmasq
systemctl enable hostapd dnsmasq dhcpcd
systemctl start hostapd dnsmasq dhcpcd

SSID=OpenBCI-Stream
PASSPHRASE=raspberrypi

function secure_file {
    if test -f $1.orig; then
        rm $1
        cp $1.orig $1
    else
        cp $1 $1.orig
    fi
}

FILE=/etc/dhcpcd.conf
secure_file $FILE
echo "
interface wlan0
static ip_address=192.168.1.1/24
" >> $FILE


FILE=/etc/dnsmasq.conf
secure_file $FILE
echo "
port=5353
interface=wlan0
dhcp-range=192.168.1.100,192.168.1.200,24h
dhcp-option=option:dns-server,192.168.1.1
" >> $FILE

FILE=/etc/default/hostapd
rm $FILE
echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' >> $FILE

FILE=/etc/hostapd/hostapd.conf
secure_file $FILE
rm $FILE
echo "
interface=wlan0
driver=nl80211
ssid=$SSID
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
wpa_passphrase=$PASSPHRASE
rsn_pairwise=CCMP
" >> $FILE

FILE=/etc/sysctl.conf
rm $FILE
echo "net.ipv4.ip_forward=1 " >> /etc/sysctl.conf

echo ""
echo "Configured Raspberry Pi as an access point"
echo "SSID:       $SSID"
echo "PASSPHRASE: $PASSPHRASE"
echo ""