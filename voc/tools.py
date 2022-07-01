# -*- coding: UTF-8 -*-
from os import path
import uuid
import json
import re
import sys
import git

from typing import Dict
from collections import OrderedDict
from bs4 import Tag

import __main__


sos_ids = {}
last_edited = {}
next_id = 1000
generated_ids = 0
uuid_namespace = uuid.UUID('0C9A24B4-72AA-4202-9F91-5A2B6BFF2E6F')
VERSION = None


def write(x):
    sys.stdout.write(x)
    sys.stdout.flush()


def set_base_id(value):
    global next_id
    next_id = value


def get_id(guid):
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
        
            next_id = max(sos_ids.values())+1


# write sos_ids to disk
def store_sos_ids():
    global sos_ids
    with open("_sos_ids.json", "w") as fp:
        json.dump(sos_ids, fp, indent=4)


def gen_random_uuid():
    return uuid.uuid4()


def gen_uuid(name):
    return str(uuid.uuid5(uuid_namespace, str(name)))


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
            if isinstance(value, (basestring, int)):
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
            if isinstance(value, (basestring, int)):
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


def parse_json(text):
    # this more complex way is necessary
    # to maintain the same order as in the input file
    return json.JSONDecoder(object_pairs_hook=OrderedDict).decode(text)


def load_json(filename):
    with open(filename, "r") as fp:
        # data = json.load(fp)
        # maintain order from file
        data = parse_json(fp.read())
    return data


def get_version():
    global VERSION
    if VERSION is None:
        repo = git.Repo(path=__file__, search_parent_directories=True)
        sha = repo.head.object.hexsha
        VERSION = repo.git.rev_parse(sha, short=5)
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
