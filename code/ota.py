#!/usr/bin/env python
# coding=utf-8
# -------------------------------------------------------------------------------
# ESPurna OTA manager
# xose.perez@gmail.com
#
# Requires PlatformIO Core
# -------------------------------------------------------------------------------
from __future__ import print_function

import argparse
import re
import socket
import subprocess
import sys
from time import sleep

from zeroconf import ServiceBrowser, ServiceStateChange, Zeroconf

try:
    # noinspection PyUnresolvedReferences
    input = raw_input  # Python2
except NameError:
    pass  # Python3

# -------------------------------------------------------------------------------

devices = []
description = "ESPurna OTA Manager v0.1"


# -------------------------------------------------------------------------------

def on_service_state_change(zeroconf, service_type, name, state_change):
    """
    Callback that adds discovered devices to "devices" list
    """

    if state_change is ServiceStateChange.Added:
        info = zeroconf.get_service_info(service_type, name)
        if info:
            hostname = info.server.split(".")[0]
            device = {
                'hostname': hostname.upper(),
                'ip': socket.inet_ntoa(info.address)
            }
            device['app'] = info.properties.get('app_name', '')
            device['version'] = info.properties.get('app_version', '')
            device['device'] = info.properties.get('target_board', '')
            device['mem_size'] = info.properties.get('mem_size', '')
            device['sdk_size'] = info.properties.get('sdk_size', '')
            devices.append(device)


def list():
    """
    Shows the list of discovered devices
    """
    output_format = "{:>3}  {:<25}{:<25}{:<15}{:<15}{:<30}{:<10}{:<10}"
    print(output_format.format(
            "#",
            "HOSTNAME",
            "IP",
            "APP",
            "VERSION",
            "DEVICE",
            "MEM_SIZE",
            "SDK_SIZE",
    ))
    print("-" * 135)

    index = 0
    for device in devices:
        index = index + 1
        print(output_format.format(
                index,
                device.get('hostname', ''),
                device.get('ip', ''),
                device.get('app', ''),
                device.get('version', ''),
                device.get('device', ''),
                device.get('mem_size', ''),
                device.get('sdk_size', ''),
        ))

    print()


def get_boards():
    """
    Grabs board types fro hardware.h file
    """
    boards = []
    for line in open("espurna/config/hardware.h"):
        m = re.search(r'defined\((\w*)\)', line)
        if m:
            boards.append(m.group(1))
    return sorted(boards)


def flash():
    """
    Grabs info from the user about what device to flash
    """

    # Choose the board
    try:
        index = int(input("Choose the board you want to flash (empty if none of these): "))
    except:
        index = 0
    if index < 0 or len(devices) < index:
        print("Board number must be between 1 and %s\n" % str(len(devices)))
        return None

    board = {'board': '', 'ip': '', 'size': 0, 'auth': '', 'flags': ''}

    if index > 0:
        device = devices[index - 1]
        board['board'] = device.get('device', '')
        board['ip'] = device.get('ip', '')
        board['size'] = int(device.get('mem_size', 0) if device.get('mem_size', 0) == device.get('sdk_size', 0) else 0) / 1024

    # Choose board type if none before
    if len(board['board']) == 0:

        print()
        count = 1
        boards = get_boards()
        for name in boards:
            print("%3d\t%s" % (count, name))
            count = count + 1
        print()
        try:
            index = int(input("Choose the board type you want to flash: "))
        except:
            index = 0
        if index < 1 or len(boards) < index:
            print("Board number must be between 1 and %s\n" % str(len(boards)))
            return None
        board['board'] = boards[index - 1]

    # Choose board size of none before
    if board['size'] == 0:
        try:
            board['size'] = int(input("Board memory size (1 for 1M, 4 for 4M): "))
        except:
            print("Wrong memory size")
            return None

    # Choose IP of none before
    if len(board['ip']) == 0:
        try:
            board['ip'] = input("IP of the device to flash (empty for 192.168.4.1): ") or "192.168.4.1"
        except:
            print("Wrong IP")
            return None

    board['auth'] = input("Authorization key of the device to flash: ")
    board['flags'] = input("Extra flags for the build: ")

    return board


def run(device, env):
    command = "export ESPURNA_IP=\"%s\"; export ESPURNA_BOARD=\"%s\"; export ESPURNA_AUTH=\"%s\"; export ESPURNA_FLAGS=\"%s\"; platformio run --silent --environment %s -t upload"
    command = command % (device['ip'], device['board'], device['auth'], device['flags'], env)
    subprocess.check_call(command, shell=True)


# -------------------------------------------------------------------------------

if __name__ == '__main__':

    # Parse command line options
    parser = argparse.ArgumentParser(description=description)
    # parser.add_argument("-v", "--verbose", help="show verbose output", default=0, action='count')
    parser.add_argument("-f", "--flash", help="flash device", default=0, action='count')
    parser.add_argument("-s", "--sort", help="sort devices list by field", default='hostname')
    args = parser.parse_args()

    print()
    print(description)
    print()
    # Enable logging if verbose
    # logging.basicConfig(level=logging.DEBUG)
    # logging.getLogger('zeroconf').setLevel(logging.DEBUG)

    # Look for sevices
    zeroconf = Zeroconf()
    browser = ServiceBrowser(zeroconf, "_arduino._tcp.local.", handlers=[on_service_state_change])
    sleep(1)
    zeroconf.close()

    # Sort list
    field = args.sort.lower()
    if field not in devices[0]:
        print("Unknown field '%s'\n" % field)
        sys.exit(1)
    devices = sorted(devices, key=lambda device: device.get(field, ''))

    # List devices
    list()

    # Flash device
    if args.flash > 0:
        device = flash()
        if device:

            env = "esp8266-%sm-ota" % device['size']

            # Summary
            print()
            print("ESPURNA_IP    = %s" % device['ip'])
            print("ESPURNA_BOARD = %s" % device['board'])
            print("ESPURNA_AUTH  = %s" % device['auth'])
            print("ESPURNA_FLAGS = %s" % device['flags'])
            print("ESPURNA_ENV   = %s" % env)

            response = input("\nAre these values right [y/N]: ")
            print()
            if response == "y":
                run(device, env)
