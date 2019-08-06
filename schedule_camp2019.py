#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import requests
import json
from collections import OrderedDict
import dateutil.parser
from datetime import datetime
import pytz
import os
import sys
import traceback
import optparse

# some functions used in multiple files of this collection
from voc.schedule import Schedule
import voc.tools

#TODO for python3: 
# * fix NameError: name 'basestring' is not defined in voc.tools.dict_to_schedule_xml()

tz = pytz.timezone('Europe/Amsterdam')

parser = optparse.OptionParser()
parser.add_option('--online', action="store_true", dest="online", default=False)
parser.add_option('--show-assembly-warnings', action="store_true", dest="show_assembly_warnings", default=False)
#parser.add_option('--fail', action="store_true", dest="exit_when_exception_occours", default=False)
parser.add_option('--git', action="store_true", dest="git", default=False)


options, args = parser.parse_args()
local = False
use_offline_frab_schedules = False
only_workshops = False


year = str(2019)
xc3 = 'camp{year}'.format(year=year)

wiki_url = 'https://events.ccc.de/camp/{year}/wiki'.format(year=year)
main_schedule_url = 'http://fahrplan.events.ccc.de/camp/{year}/Fahrplan/schedule.json'.format(year=year)
additional_schedule_urls = [
    { 'name': 'thm',     'url': 'https://talx.thm.cloud/thms/schedule/export/schedule.json',    'id_offset': 100},
#    { 'name': 'lounges',        'url': 'https://fahrplan.events.ccc.de/congress/2018/Lineup/schedule.json',             'id_offset': None},
#    { 'name': 'komona',         'url': 'https://talks.komona.org/35c3/schedule/export/schedule.json',                   'id_offset': 800},
#    { 'name': 'lightning',      'url': 'https://c3lt.de/35c3/schedule/export/schedule.json',                            'id_offset': 3000}
]


# this list/map is required to sort the events in the schedule.xml in the correct way
# other rooms/assemblies are added at the end on demand.
rooms = [ 
]

output_dir = "/srv/www/" + xc3
secondary_output_dir = "./" + xc3
#validator = sys.path[0] + "/validator/xsd/validate_schedule_xml.sh"
validator = "xmllint --noout --schema {path}/validator/xsd/schedule-without-person.xml.xsd".format(path=sys.path[0])

if len(sys.argv) == 2:
    output_dir = sys.argv[1]

if not os.path.exists(output_dir):
    try:
        if not os.path.exists(secondary_output_dir):
            os.mkdir(output_dir) 
        else:
            output_dir = secondary_output_dir
            local = True
    except:
        print('Please create directory named {} if you want to run in local mode'.format(secondary_output_dir))
        exit(-1)
os.chdir(output_dir)


def get_schedule(name, url):
    if use_offline_frab_schedules:
        # python3: , encoding='utf-8'
        with open("schedule_{}.json".format(name), "r") as fp:
            return parse_json(fp.read())
    else:
        print("Requesting " + url)
        schedule_r = requests.get(url) #, verify=False)
        
        if schedule_r.ok is False:
            raise Exception("  Request failed, HTTP {0}.".format(schedule_r.status_code))

        schedule = parse_json(schedule_r.text)
        return schedule

def parse_json(text):
    # this more complex way is necessary 
    # to maintain the same order as in the input file
    return json.JSONDecoder(object_pairs_hook=OrderedDict).decode(text)


def export_schedule(filename, schedule):
    print('  writing files...')
    with open("{}.schedule.json".format(filename), "w") as fp:
        json.dump(schedule, fp, indent=4)
    
    with open('{}.schedule.xml'.format(filename), 'w') as fp:
        fp.write(Schedule(json=schedule).xml())

    sys.stdout.write('  ')
    sys.stdout.flush()

    # validate xml
    os.system('{} {}.schedule.xml'.format(validator, filename))




def main():
    global full_schedule
        
    main_schedule = get_schedule('main_rooms', main_schedule_url)

    full_schedule = main_schedule.copy()

    # add rooms now, so they are in the correct order
    for day in full_schedule["schedule"]["conference"]["days"]:
        for key in rooms:
            if key not in day['rooms']:
                day['rooms'][key] = list()

    # add frab events from additional_schedule's to full_schedule
    for entry in additional_schedule_urls:
        try:
            other_schedule = get_schedule(entry['name'], entry['url'])
            
            if add_events_from_frab_schedule(other_schedule, id_offset=entry.get('id_offset'), options=entry.get('options')):
                print("  success")
            if 'version' in other_schedule["schedule"]:
                full_schedule["schedule"]["version"] += " " + other_schedule["schedule"]["version"]
            else:
                print('  WARNING: schedule "{}" does not have a version number'.format(entry['name']))

        except:
            print("  UNEXPECTED ERROR:" + str(sys.exc_info()[1]))

    print("Processing...")

    # write all events to one big schedule.json/xml  
    export_schedule("everything", full_schedule)
    
    print('Done')

def add_events_from_frab_schedule(other_schedule, id_offset = None, options = None):
    global full_schedule

    primary_start = dateutil.parser.parse(full_schedule["schedule"]["conference"]["start"])
    other_start = dateutil.parser.parse(other_schedule["schedule"]["conference"]["start"])
    offset = (other_start - primary_start).days

    try:
        while other_schedule["schedule"]["conference"]["days"][offset]["date"] != full_schedule["schedule"]["conference"]["days"][0]["date"]:
            offset += 1
    except:
        print("  ERROR: no overlap between other schedule and primary schedule")
        return False

    for day in other_schedule["schedule"]["conference"]["days"]:
        target_day = day["index"] - 1 + offset 

        if target_day < 0:
            print( "  ignoring day {} from {}, as primary schedule starts at {}".format(
                day["date"], other_schedule["schedule"]["conference"]["acronym"], full_schedule["schedule"]["conference"]["start"]) 
            )
            continue

        if day["date"] != full_schedule["schedule"]["conference"]["days"][target_day]["date"]:
            print(target_day)
            print("  WARNING: the other schedule's days have to match primary schedule, in some extend!")
            return False
    
        for room in day["rooms"]:
            target_room = room
            if options and 'room-map' in options and room in options['room-map']:
                target_room = options['room-map'][room]

            if id_offset:
                for event in day["rooms"][room]:
                    event['id'] = int(event['id']) + id_offset
                    event['room'] = target_room
                # TODO? offset for person IDs?

            full_schedule["schedule"]["conference"]["days"][target_day]["rooms"][target_room] = day["rooms"][room]
        
    
    return True



if __name__ == '__main__':
    main()
    

    if not local or options.git:      
        content_did_not_change = os.system('/usr/bin/env git diff -U0 --no-prefix | grep -e "^[+-]  " | grep -v version > /dev/null')

        def git(args):
            os.system('/usr/bin/env git {}'.format(args))

        if content_did_not_change:
            print('nothing relevant changed, reverting to previous state')
            git('reset --hard')
        else:
            git('add *.json *.xml')
            git('commit -m "version {} with {} new self-organized session(s)"'.format(full_schedule["schedule"]["version"], voc.tools.generated_ids))
            git('push')
