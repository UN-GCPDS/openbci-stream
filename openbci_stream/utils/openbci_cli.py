"""
======================
Command line interface
======================

This interface is useful to debug, test connections and features. It can be used
for start acquisition or simply connect to an existing one, stream markers, and
storage data.


For examples and descriptions refers to documentation:
`Data storage handler <../06-command_line_interface.ipynb>`_
"""

# import os
import sys
import signal
import pickle
import logging
import argparse
from datetime import datetime

# import numpy as np
from kafka import KafkaProducer
from colorama import Fore

from openbci_stream.utils import HDF5Writer
# from .hdf5 import HDF5Writer
from openbci_stream.acquisition import CytonRFDuino, CytonWiFi, OpenBCIConsumer
# from ..acquisition import CytonRFDuino, CytonWiFi, OpenBCIConsumer

# Disable Kafka loggings
logging.getLogger().disabled = True
logging.getLogger('kafka.coordinator.consumer').disabled = True
logging.getLogger('kafka.consumer.fetcher').disabled = True

# Command line parser
parser = argparse.ArgumentParser(prog="openbci_cli",
                                 description="Command line interface for OpenBCI-Stream",
                                 epilog="OpenBCI-Stream is software package developed by GCPDS",
                                 allow_abbrev=True)

# -----------------------------------------------------------------------------
# Parent for Serial, and WiFi
parent_parser = argparse.ArgumentParser(add_help=False)

# Start and Stop
group_stream = parent_parser.add_mutually_exclusive_group()
# group_stream.add_argument('--start', action='store_true', help='Start stream')
# group_stream.add_argument('--stop', action='store_true', help='Stop stream')

# Extra commands
parent_parser.add_argument("-c", "--command", action='extend',
                           nargs="+", help="Send commands after connection established")

# Stream samples
parent_parser.add_argument("-s", "--streaming_package_size", action='store', default=250,
                           type=int,
                           help='Number of samples to receive in stream')

# Daisy
parent_parser.add_argument("-d", "--daisy", action='store_true',
                           help='Enable or disable daisy')

# -----------------------------------------------------------------------------
# Common parsers
common_parser = argparse.ArgumentParser(add_help=False)

# Host
common_parser.add_argument("--host", action='store', default='localhost',
                           help='Hostname where is running the acquisition system')

# Output EEG
common_parser.add_argument("--output", action='store',
                           type=str, help='Write stream into file')

# # Output Marker
# common_parser.add_argument("--output_markers", action='store',
                           # type=argparse.FileType('wb'),
                           # help='Write markers into file')

# -----------------------------------------------------------------------------
# Interface
subparser_mode = parser.add_subparsers(title='Endpoint', required=True,
                                       dest='endpoint',)

# Serial and Port
subparser_serial = subparser_mode.add_parser('serial',
                                             parents=[parent_parser,
                                                      common_parser],
                                             help='Endpoint using Serial protocol')
subparser_serial.add_argument('--port', help='Serial port')

# WiFi and IP
subparser_wifi = subparser_mode.add_parser('wifi',
                                           parents=[parent_parser,
                                                    common_parser],
                                           help='Endpoint  using WiFi module')
subparser_wifi.add_argument('--ip', help='IP for WiFi module')

# Stream
subparser_stream = subparser_mode.add_parser('stream', parents=[common_parser],
                                             help='Real-time transmission packages debugger')
# subparser_stream.add_argument('--output', help='')

# Marker
subparser_marker = subparser_mode.add_parser('marker', parents=[common_parser],
                                             help='Real-time markers streamer')


# ----------------------------------------------------------------------
def main():
    """"""

    try:
        args = parser.parse_args()
    except Exception:
        parser.print_help()
        sys.exit()

    # ----------------------------------------------------------------------
    def handle_ctrl_c(*_):
        """"""
        if args.output:
            writer.close()
        try:
            interface.stop_stream()
        except:
            pass
        finally:
            sys.exit()

    signal.signal(signal.SIGINT, handle_ctrl_c)

    started = False
    if args.endpoint in ['serial', 'wifi']:

        if args.endpoint == 'serial':
            interface = CytonRFDuino(port=args.port, host=args.host,
                                     daisy=args.daisy,
                                     capture_stream=False,
                                     montage=None,
                                     streaming_package_size=args.streaming_package_size
                                     )

        elif args.endpoint == 'wifi':
            interface = CytonWiFi(args.ip,
                                  daisy=args.daisy,
                                  host=args.host,
                                  capture_stream=False,
                                  montage=None,
                                  streaming_package_size=args.streaming_package_size
                                  )

        if args.command:
            for command in args.command:
                interface.command(command.encode())

        interface.start_stream()
        started = True

    if args.endpoint == 'stream' or args.output or started:

        with OpenBCIConsumer(host=args.host) as stream:

            if args.output:
                writer = HDF5Writer(args.output)
                header = {'sample_rate': args.streaming_package_size,
                          'datetime': datetime.now().timestamp(),
                          # 'montage': 'standard_1020',
                          # 'ch_names': 'Fp1,Fp2,F7,Fz,F8,C3,Cz,C4,T5,P3,Pz,P4,T6,O1,Oz,O2'.split(','),
                          }
                writer.add_header(header)

            print(f"Writing data in {Fore.LIGHTYELLOW_EX}{Fore.RESET}\n"
                  f"{Fore.LIGHTYELLOW_EX}Ctrl+C{Fore.RESET} for stop it.\n")
            for message in stream:

                if message.topic == 'eeg':

                    eeg, aux = message.value['data']
                    created = datetime.fromtimestamp(
                        message.value['binary_created'])
                    since = (datetime.now() - created).total_seconds()
                    count = message.value['samples']
                    channels = eeg.shape[0]

                    print(f"{Fore.YELLOW}[EEG]{Fore.RESET} {Fore.LIGHTYELLOW_EX}{created}{Fore.RESET}\t"
                          f"{Fore.LIGHTRED_EX if since>1 else Fore.RESET}{since:0.4f}s ago{Fore.RESET}\t"
                          f"{count} samples, {channels} channels")

                    if args.output:
                        writer.add_eeg(eeg.T, created.timestamp())

                if message.topic == 'marker':

                    marker = message.value
                    created = datetime.fromtimestamp(message.timestamp / 1000)
                    since = (datetime.now() - created).total_seconds()
                    print(f"{Fore.YELLOW}[MKR]{Fore.RESET} {Fore.LIGHTYELLOW_EX}{created}{Fore.RESET}\t"
                          f"{Fore.LIGHTRED_EX if since>1 else Fore.RESET}{since*1000:0.4f} ms ago{Fore.RESET}\t"
                          f"{Fore.LIGHTBLUE_EX}{marker}{Fore.RESET}")

                    if args.output:
                        writer.add_marker(marker, created.timestamp())

            if args.output:
                writer.close()

    if args.endpoint == 'marker':

        producer_eeg = KafkaProducer(bootstrap_servers=[f'{args.host}:9092'],
                                     # compression_type='gzip',
                                     value_serializer=pickle.dumps,
                                     )

        while True:
            marker = input(f'{Fore.YELLOW}>>> {Fore.RESET}')
            if mkr := marker.strip():
                producer_eeg.send(
                    'marker', {'timestamp': datetime.now().timestamp(), 'marker': mkr})


if __name__ == '__main__':
    main()
