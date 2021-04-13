#!/usr/bin/bash

function secure_file {
    if test -f $1.orig; then
        rm $1
        cp $1.orig $1
    else
        cp $1 $1.orig
    fi
}

pacman -S --needed ntp

FILE=/etc/ntp.conf
secure_file $FILE
rm $FILE
echo "
# Please consider joining the pool:
#
#     http://www.pool.ntp.org/join.html
#
# For additional information see:
# - https://wiki.archlinux.org/index.php/Network_Time_Protocol_daemon
# - http://support.ntp.org/bin/view/Support/GettingStarted
# - the ntp.conf man page

tinker panic 0

# Associate to Arch's NTP pool
server 0.arch.pool.ntp.org
server 1.arch.pool.ntp.org
server 2.arch.pool.ntp.org
server 3.arch.pool.ntp.org

tos orphan 5

# Fallback to local clock if all else fails
server  127.127.1.0     # local clock
fudge   127.127.1.0 stratum 16

# By default, the server allows:
# - all queries from the local host
# - only time queries from remote hosts, protected by rate limiting and kod
restrict default kod limited nomodify nopeer noquery notrap
restrict 191.168.1.0 mask 255.255.255.0 nomodify notrap
restrict 127.0.0.1
restrict -6 ::1
restrict ::1

# Location of drift file
driftfile /var/lib/ntp/ntp.drift
" >> $FILE

systemctl enable ntpd
systemctl start ntpd