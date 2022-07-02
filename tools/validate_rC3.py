#!/usr/bin/env python3

import argparse
import json
import requests
import sys

import logging
logger = logging.getLogger(__name__)


def configure_logging(level = logging.INFO):
    logging.addLevelName(logging.CRITICAL, '\033[1;41m%s\033[1;0m' % logging.getLevelName(logging.CRITICAL))
    logging.addLevelName(logging.ERROR, '\033[1;31m%s\033[1;0m' % logging.getLevelName(logging.ERROR))
    logging.addLevelName(logging.WARNING, '\033[1;33m%s\033[1;0m' % logging.getLevelName(logging.WARNING))
    logging.addLevelName(logging.INFO, '\033[1;32m%s\033[1;0m' % logging.getLevelName(logging.INFO))
    logging.addLevelName(logging.DEBUG, '\033[1;34m%s\033[1;0m' % logging.getLevelName(logging.DEBUG))

    log_format = '%(levelname)s: %(message)s'
    logging.basicConfig(level=level, format=log_format)


def check_roomnames(channels_url, streamconfig_url, ignores=[]):
    channel_rooms = []
    stream_rooms = []
    missing_rooms = []
    channels = requests.get(channels_url).json()
    streamconfig = requests.get(streamconfig_url).json()

    for channel in channels['data']['channels']:
        channel_rooms.append(channel['stage'])

    for room in streamconfig[0]['conference']['rooms']:
        if room['streamingConfig']['display'] in ignores:
            logger.info(f"(skipping '{room['streamingConfig']['display']}' room)")
            continue
        if 'schedule_name' in room['streamingConfig'] \
                and room['streamingConfig']['schedule_name'] != "":
            stream_rooms.append(room['streamingConfig']['schedule_name'])
        else:
            logger.warning(f"streamconfig room has no schedule_name: {room['name']}")

    for room in stream_rooms:
        if room in ignores:
            logger.info(f"(skipping channel match for streamconfig room '{room}')")
            continue
        if room in channel_rooms:
            logger.info(f"stream room OK: {room}")
            channel_rooms.remove(room)
        else:
            logger.error(f"streamconfig room has no channel match: {room}")
            missing_rooms.append(room)

    for room in channel_rooms:
        if room in ignores:
            logger.info(f"(skipping stream config match for channel room '{room}')")
            continue
        logger.warning(f"channel room not in stream config: {room}")

    if len(missing_rooms) > 0:
        print("no channel for rooms:", ', '.join(missing_rooms))
    return len(missing_rooms)

def main():
    parser = argparse.ArgumentParser(description='rc3 channelconfig validator')
    parser.add_argument('channels_url', metavar='CHANNELS-URL', type=str,
                        help='url for the channels json')
    parser.add_argument('streamconfig_url', metavar='STREAMCONFIG-URL', type=str,
                        help='url for the stream config json')
    parser.add_argument('-i', metavar='IGNOREDNAME', type=str, nargs='*',
                        help='ignored channel name', required=False, default=[])
    args = parser.parse_args()

    return check_roomnames(args.channels_url, args.streamconfig_url, args.i)

if __name__ == "__main__":
    configure_logging()
    sys.exit(main())
