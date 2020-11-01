"""
=================
Scan WiFi modules
=================
"""

import requests
from typing import Dict


# ----------------------------------------------------------------------
def scan_wifi_modules(network: str = "wlan0") -> Dict[str, str]:
    """Scan for WiFi modules.

    Explore the local network with `nmap` in search of WiFi modules, the way to
    check if a device is a WiFi module is reading the `/board` endopint, the
    `JSON` is stored and returned too.

    Parameters
    ----------
    network
        The network interface name used e.g. `wlan0`, `wlp2s0`, 'eth0'...

    Returns
    -------
    dict
        Dictionay with IPs as keys of WiFi modules on network and `/board` as
        value.
    """

    # Optional requieres are imported only inside the function
    import netifaces
    import nmap

    ip_list = {}
    local_net = netifaces.ifaddresses(network)[netifaces.AF_INET][0]["addr"]

    nm = nmap.PortScanner()
    nm.scan(hosts=f"{local_net}/24", arguments="-sn")
    hosts = nm.all_hosts()

    for host in hosts:
        try:
            response = requests.get(f"http://{host}/board", timeout=0.1)
            if response.ok:
                ip_list[host] = response.json()
        except:
            continue

    return ip_list


if __name__ == "__main__":
    print(scan_wifi_modules())
