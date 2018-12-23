# -*- coding: UTF-8 -*-

from collections import OrderedDict
import uuid
import json
import re
import sys

sos_ids = {}
next_id = 1000
generated_ids = 0
uuid_namespace = uuid.UUID('0C9A24B4-72AA-4202-9F91-5A2B6BFF2E6F')

def set_base_id(value):
    global next_id
    next_id = value

def get_id(guid):
    global sos_ids, next_id, generated_ids
    if guid not in sos_ids:
        #generate new id
        sos_ids[guid] = next_id
        next_id += 1
        generated_ids += 1
    
    return sos_ids[guid]

def gen_random_uuid():
    return uuid.uuid4()

def gen_uuid(name):
    return str(uuid.uuid5(uuid_namespace, str(name)))

# depreacated, use Schedule.foreach_event() instead
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
                ret[key] = copy_base_structure_list(value, level-1) 
            else:
                ret[key] = copy_base_structure(value, level-1) 
    return ret

def copy_base_structure_list(subtree, level):
    ret = []
    if level > 0:
        for value in subtree:
            if isinstance(value, (basestring, int)):
                ret.append(value)
            elif isinstance(value, list):
                ret.append(copy_base_structure_list(value, level-1))
            else:
                ret.append(copy_base_structure(value, level-1)) 
    return ret


def normalise_string(string):
    string = string.lower()
    string = string.replace(u"ä", 'ae')
    string = string.replace(u'ö', 'oe')
    string = string.replace(u'ü', 'ue')
    string = string.replace(u'ß', 'ss')
    string = re.sub('\W+', '\_', string.strip()) # replace whitespace with _
    # string = filter(unicode.isalnum, string)
    string = re.sub('[^a-z0-9_]+', '', string) # TODO: is this not already done with \W+  line above?

    return string

def normalise_time(timestr):
    timestr = timestr.replace('p.m.', 'pm')
    timestr = timestr.replace('a.m.', 'am')
    ## workaround for failure in input file format
    if timestr.startswith('0:00'):
        timestr = timestr.replace('0:00', '12:00')
        
    return timestr

def parse_json(text):
    # this more complex way is necessary 
    # to maintain the same order as in the input file
    return json.JSONDecoder(object_pairs_hook=OrderedDict).decode(text)