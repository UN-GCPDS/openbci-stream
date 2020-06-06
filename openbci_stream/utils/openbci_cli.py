from openbci_stream.consumer import OpenBCIConsumer
from openbci_stream.acquisition import CytonRFDuino, CytonWiFi
from colorama import Fore, Back, Style
import argparse
import sys
from datetime import datetime
import numpy as np
import signal
import logging
from kafka import KafkaProducer
import pickle

logging.getLogger().disabled = True
logging.getLogger('kafka.coordinator.consumer').disabled = True
logging.getLogger('kafka.consumer.fetcher').disabled = True


# from openbci_stream.acquisition.cyton_base import CytonBase

parser = argparse.ArgumentParser(prog="openbci_cli", description="Command line interface for OpenBCI-Stream",
                                 epilog="OpenBCI-Stream is software package developed by GCPDS", allow_abbrev=True)


# -----------------------------------------------------------------------------
# Parent for Serial, and WiFi
parent_parser = argparse.ArgumentParser(add_help=False)

# Start and Stop
group_stream = parent_parser.add_mutually_exclusive_group()
group_stream.add_argument(
    '--start', action='store_true', help='Start stream')
group_stream.add_argument('--stop', action='store_true', help='Stop stream')

# Extra commands
parent_parser.add_argument("-c", "--command", action='extend', nargs="+",
                           help="Send commands after connection established")

# Stream samples
parent_parser.add_argument("--stream_samples", action='store', default=250, type=int,
                           help='Number of samples to receive in stream')

# Daisy
parent_parser.add_argument("--daisy", action='store_true',
                           help='Enable or disable daisy')

# -----------------------------------------------------------------------------
# Common parsers
common_parser = argparse.ArgumentParser(add_help=False)

# Host
common_parser.add_argument("--host", action='store', default='localhost',
                           help='Hostname were running acquisition system')

# Output EEG
common_parser.add_argument("--output", action='store', type=argparse.FileType('wb'),
                           help='Write stream into file')

# Output Marker
common_parser.add_argument("--output_markers", action='store', type=argparse.FileType('wb'),
                           help='Write markers into file')

# -----------------------------------------------------------------------------

subparser_mode = parser.add_subparsers(
    title='Interface', required=True, dest='interface',)

# Serial and Port
subparser_serial = subparser_mode.add_parser(
    'serial', parents=[parent_parser, common_parser], help='Interface using Serial protocol')
subparser_serial.add_argument('--port', help='Serial port')

# WiFi and IP
subparser_wifi = subparser_mode.add_parser(
    'wifi', parents=[parent_parser, common_parser], help='Interface using WiFi module')
subparser_wifi.add_argument('--ip', help='IP for WiFi module')

# Stream
subparser_stream = subparser_mode.add_parser(
    'stream', parents=[common_parser], help='')
# subparser_stream.add_argument('--output', help='')

# Marker
subparser_marker = subparser_mode.add_parser(
    'marker', parents=[common_parser], help='')


try:
    args = parser.parse_args()
except Exception as e:
    # print(e)
    parser.print_help()
    sys.exit()


# ----------------------------------------------------------------------
def main():
    """"""

    # ----------------------------------------------------------------------
    def handle_ctrl_c(*_):
        """"""
        if args.output:
            args.output.close()
        if args.output_markers:
            args.output_markers.close()

        try:
            interface.stop_stream()
        except:
            pass
        finally:

            sys.exit()

    signal.signal(signal.SIGINT, handle_ctrl_c)

    if args.interface in ['serial', 'wifi']:

        if args.stream_samples:
            kwargs = {'stream_samples': args.stream_samples}
        else:
            kwargs = {}

        if args.interface == 'serial':
            interface = CytonRFDuino(port=args.port, host=args.host, daisy=args.daisy,
                                     capture_stream=False,
                                     montage=None,
                                     **kwargs,
                                     # stream_samples=args.stream_samples
                                     )

        elif args.interface == 'wifi':
            interface = CytonWiFi(args.ip,
                                  daisy=args.daisy,
                                  host=args.host,
                                  capture_stream=False,
                                  montage=None,
                                  **kwargs,
                                  # stream_samples=args.stream_samples
                                  )

        if args.command:
            for command in args.command:
                interface.command(command.encode())

        if args.start:
            interface.start_stream()
        elif args.stop:
            interface.stop_stream()

    if args.interface == 'stream' or args.output or args.output_markers:

        with OpenBCIConsumer(host=args.host) as stream:

            if args.output or args.output_markers:
                print(
                    f"Writing data in {Fore.LIGHTYELLOW_EX}{Fore.RESET}\n{Fore.LIGHTYELLOW_EX}Ctrl+C{Fore.RESET} for stop it.\n")

            for message in stream:

                if message.topic == 'eeg':

                    eeg, aux = message.value['data']
                    created = datetime.fromtimestamp(
                        message.value['binary_created'])
                    since = (datetime.now() - created).total_seconds()
                    count = message.value['samples']
                    channels = eeg.shape[0]

                    print(
                        f"{Fore.YELLOW}[EEG]{Fore.RESET} {Fore.LIGHTYELLOW_EX}{created}{Fore.RESET}\t{Fore.LIGHTRED_EX if since>1 else Fore.RESET}{since:0.4f}s ago{Fore.RESET}\t{count} samples, {channels} channels")

                    timestamp = np.zeros(count)
                    timestamp[0] = created.timestamp()
                    timestamp = timestamp.reshape(count, 1)
                    timestamp[timestamp == 0] = None

                    if args.output:
                        np.savetxt(args.output, np.concatenate(
                            [timestamp, eeg.T], axis=1), delimiter=',')

                if message.topic == 'marker':

                    marker = message.value['marker']
                    created = datetime.fromtimestamp(
                        message.value['timestamp'])
                    since = (datetime.now() - created).total_seconds()
                    print(f"{Fore.YELLOW}[MKR]{Fore.RESET} {Fore.LIGHTYELLOW_EX}{created}{Fore.RESET}\t{Fore.LIGHTRED_EX if since>1 else Fore.RESET}{since:0.4f}s ago{Fore.RESET}\t{Fore.LIGHTBLUE_EX}{marker}{Fore.RESET}")

                    if args.output_markers:
                        np.savetxt(args.output_markers, np.array(
                            [[created.timestamp(), marker]]), delimiter=',', fmt='%s')

            if args.output:
                args.output.close()

            if args.output_markers:
                args.output_markers.close()

    if args.interface == 'marker':

        producer_eeg = KafkaProducer(bootstrap_servers=[f'{args.host}:9092'],
                                     # compression_type='gzip',
                                     value_serializer=lambda x: pickle.dumps(
                                         x),
                                     )

        while True:
            marker = input(f'{Fore.YELLOW}>>> {Fore.RESET}')
            if mkr := marker.strip():
                producer_eeg.send(
                    'marker', {'timestamp': datetime.now().timestamp(), 'marker': mkr})


if __name__ == '__main__':
    main()
