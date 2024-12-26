# -*- coding: UTF-8 -*-
from datetime import timedelta
from logging import Logger
import argparse
from os import path
import os
import uuid
import json
import re
import sys

from typing import Dict, Union
from collections import OrderedDict
from bs4 import Tag
from git import Repo

import __main__

sos_ids = {}
last_edited = {}
next_id = 1000
generated_ids = 0
NAMESPACE_VOC = uuid.UUID('0C9A24B4-72AA-4202-9F91-5A2B6BFF2E6F')
VERSION = None

log = Logger(__name__)

def DefaultOptionParser(local=False):
    parser = argparse.ArgumentParser()
    parser.add_argument("--online", action="store_true", dest="online", default=False)
    parser.add_argument(
        "--fail", action="store_true", dest="exit_when_exception_occours", default=local
    )
    parser.add_argument("--stats", action="store_true", dest="only_stats", default=False)
    parser.add_argument("--git", action="store_true", dest="git", default=False)
    parser.add_argument("--debug", action="store_true", dest="debug", default=local)
    return parser

def write(x):
    sys.stdout.write(x)
    sys.stdout.flush()


def set_base_id(value):
    global next_id
    next_id = value


def get_id(guid, length=None):
    # use newer mode without external state if length is set
    if length:
        # generate numeric id from first x numbers from guid, stipping leading zeros
        return int(re.sub("^0+", "", re.sub("[^0-9]+", "", guid))[0:length])
    
    global sos_ids, next_id, generated_ids
    if guid not in sos_ids:
        # generate new id
        sos_ids[guid] = next_id
        next_id += 1
        generated_ids += 1

    return sos_ids[guid]


def load_sos_ids():
    global sos_ids, next_id, generated_ids
    if path.isfile("_sos_ids.json"):
        with open("_sos_ids.json", "r") as fp:
            # maintain order from file
            temp = fp.read()
            sos_ids = json.JSONDecoder(object_pairs_hook=OrderedDict).decode(temp)
        
            next_id = max(sos_ids.values()) + 1


# write sos_ids to disk
def store_sos_ids():
    global sos_ids
    with open("_sos_ids.json", "w") as fp:
        json.dump(sos_ids, fp, indent=4)


def gen_random_uuid():
    return uuid.uuid4()


def gen_person_uuid(email):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'acct:' + email))


def gen_uuid(value):
    return str(uuid.uuid5(NAMESPACE_VOC, str(value)))


# deprecated, use Schedule.foreach_event() instead
# TODO remove
def foreach_event(schedule, func):
    out = []
    for day in schedule["schedule"]["conference"]["days"]:
        for room in day['rooms']:
            for event in day['rooms'][room]:
                out.append(func(event))

    return out


def copy_base_structure(subtree, level):
    ret = OrderedDict()
    if level > 0:
        for key, value in subtree.iteritems():
            if isinstance(value, (str, int)):
                ret[key] = value
            elif isinstance(value, list):
                ret[key] = copy_base_structure_list(value, level - 1)
            else:
                ret[key] = copy_base_structure(value, level - 1)
    return ret


def copy_base_structure_list(subtree, level):
    ret = []
    if level > 0:
        for value in subtree:
            if isinstance(value, (str, int)):
                ret.append(value)
            elif isinstance(value, list):
                ret.append(copy_base_structure_list(value, level - 1))
            else:
                ret.append(copy_base_structure(value, level - 1))
    return ret


def normalise_string(string):
    string = string.lower()
    string = string.replace(u"ä", 'ae')
    string = string.replace(u'ö', 'oe')
    string = string.replace(u'ü', 'ue')
    string = string.replace(u'ß', 'ss')
    string = re.sub('\W+', '\_', string.strip())  # replace whitespace with _
    # string = filter(unicode.isalnum, string)
    string = re.sub('[^a-z0-9_]+', '', string) # TODO: is this not already done with \W+  line above?
    string = string.strip('_')  # remove trailing _

    return string


def normalise_time(timestr):
    timestr = timestr.replace('p.m.', 'pm')
    timestr = timestr.replace('a.m.', 'am')
    # workaround for failure in input file format
    if timestr.startswith('0:00'):
        timestr = timestr.replace('0:00', '12:00')

    return timestr


def format_duration(value: Union[int, timedelta]) -> str: 
    if type(value) == timedelta:
        minutes = round(value.total_seconds() / 60)
    else:
        minutes = value

    return '%d:%02d' % divmod(minutes, 60)


# from https://git.cccv.de/hub/hub/-/blob/develop/src/core/utils.py
_RE_STR2TIMEDELTA = re.compile(r'((?P<hours>\d+?)hr?\s*)?((?P<minutes>\d+?)m(ins?)?\s*)?((?P<seconds>\d+?)s)?')

def str2timedelta(s):
    if ':' in s:
        parts = s.split(':')
        kwargs = {'seconds': int(parts.pop())}
        if parts:
            kwargs['minutes'] = int(parts.pop())
        if parts:
            kwargs['hours'] = int(parts.pop())
        if parts:
            kwargs['days'] = int(parts.pop())
        return timedelta(**kwargs)

    parts = _RE_STR2TIMEDELTA.match(s)
    if not parts:
        return
    parts = parts.groupdict()
    time_params = {}
    for name, param in parts.items():
        if param:
            time_params[name] = int(param)
    return timedelta(**time_params)

def parse_json(text):
    # this more complex way is necessary
    # to maintain the same order as in the input file in python2
    return json.JSONDecoder(object_pairs_hook=OrderedDict).decode(text)


def load_json(filename):
    with open(filename, "r") as fp:
        # data = json.load(fp)
        # maintain order from file
        data = parse_json(fp.read())
    return data


def get_version():
    global VERSION
    try:
        if VERSION is None:
            repo = Repo(path=__file__, search_parent_directories=True)
            sha = repo.head.object.hexsha
            VERSION = repo.git.rev_parse(sha, short=5)
    except ValueError:
        pass
    return VERSION


def generator_info():
    module = path.splitext(path.basename(__main__.__file__))[0] \
        .replace('schedule_', '')
    return ({
        "name": "voc/schedule/" + module,
        "version": get_version()
    })


def parse_html_formatted_links(td: Tag) -> Dict[str, str]:
    """
    Returns a dictionary containing all HTML formatted links found 
    in the given table row.

    - Key: The URL of the link.
    - Value: The title of the link. Might be the same as the URL.

    :param td: A table row HTML tag.
    """
    links = {}
    for link in td.find_all("a"):
        href = link.attrs["href"]
        title = link.attrs["title"].strip()
        text = link.get_text().strip()
        links[href] = title if text is None else text

    return links


def ensure_folders_exist(output_dir, secondary_output_dir):
    global local
    local = False
    if not os.path.exists(output_dir):
        try:
            if not os.path.exists(secondary_output_dir):
                os.mkdir(output_dir)
            else:
                output_dir = secondary_output_dir
                local = True
        except Exception:
            print('Please create directory named {} if you want to run in local mode'.format(secondary_output_dir))
            exit(-1)
    os.chdir(output_dir)

    if not os.path.exists('events'):
        os.mkdir('events')

    return local


def export_filtered_schedule(output_name, parent_schedule, filter):
    write('\nExporting {} schedule... '.format(output_name))
    schedule = parent_schedule.copy(output_name)
    for day in schedule.days():
        room_keys = list(day['rooms'].keys())
        for room_key in room_keys:
            if not filter(room_key):
                del day['rooms'][room_key]

    print('\n  {}: '.format(output_name))
    for room in schedule.rooms():
        print('   - {}'.format(room))

    schedule.export(output_name)
    return schedule


def git(args):
    os.system(f'/usr/bin/env git {args}')


def commit_changes_if_something_relevant_changed(schedule):
    content_did_not_change = os.system("/usr/bin/env git diff -U0 --no-prefix | grep -e '^[+-]  ' | grep -v version > /dev/null")

    if content_did_not_change:
        print('nothing relevant changed, reverting to previous state')
        git('reset --hard')
        exit(0)

    git('add *.json *.xml events/*.json')
    git('commit -m "version {}"'.format(schedule.version()))
    git('push')


# remove talks starting before 9 am
def remove_too_early_events(room):
    from .schedule import Event

    for e in room:
        event = e if isinstance(e, Event) else Event(e)
        start_time = event.start
        if start_time.hour > 4 and start_time.hour < 9:
            print('removing {} from full schedule, as it takes place at {} which is too early in the morning'.format(event['title'], start_time.strftime('%H:%M')))
            room.remove(event)
        else:
            break


# harmonize event types
def harmonize_event_type(event, options):
    type_mapping = {

        # TALKS
        'talk': 'Talk',
        'talk/panel': 'Talk',
        'vortrag': 'Talk',
        'lecture': 'Talk',
        'beitrag': 'Talk',
        'track': 'Talk',
        'live on stage': 'Talk',
        'recorded': 'Talk',
        '60 min Talk + 15 min Q&A': 'Talk',
        '30 min Short Talk + 10 min Q&A': 'Talk',

        # LIGHTNING TALK
        'lightningtalk': 'Lightning Talk',
        'lightning_talk': 'Lightning Talk',
        'lightning-talk': 'Lightning Talk',
        'Lightning': 'Lightning Talk',

        # MEETUP
        'meetup': 'Meetup',

        # OTHER
        'other': 'Other',
        '': 'Other',
        'Pausenfüllmaterial': 'Other',

        # PODIUM
        'podium': 'Podium',

        # PERFORMANCE
        'theater': 'Performance',
        'performance': 'Performance',

        # CONCERT
        'konzert': 'Concert',
        'concert': 'Concert',

        # DJ Set
        'dj set': 'DJ Set',
        'DJ Set': 'DJ Set',

        # WORKSHOP
        'workshop': 'Workshop',

        # LIVE-PODCAST
        'Live-Podcast': 'Live-Podcast',
    }

    type = event.get('type', '').split(' ')
    if not type or not type[0]:
        event['type'] = 'Other'
    elif event.get('type') in type_mapping:
        event['type'] = type_mapping[event['type']]
    elif event.get('type').lower() in type_mapping:
        event['type'] = type_mapping[event['type'].lower()]
    elif type[0] in type_mapping:
        event['type'] = type_mapping[type[0]]
    elif type[0].lower() in type_mapping:
        event['type'] = type_mapping[type[0].lower()]
    elif options.debug:
        log.debug(f"Unknown event type: {event['type']}")

    if event.get('language') is not None:
        event['language'] = event['language'].lower()

