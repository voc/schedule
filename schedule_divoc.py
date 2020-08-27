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
from voc.schedule import Schedule, ScheduleEncoder, Event, set_validator_filter

tz = pytz.timezone('Europe/Amsterdam')

parser = optparse.OptionParser()
parser.add_option('--online', action="store_true", dest="online", default=False)
parser.add_option('--show-assembly-warnings', action="store_true", dest="show_assembly_warnings", default=False)
parser.add_option('--fail', action="store_true", dest="exit_when_exception_occours", default=False)
parser.add_option('--git', action="store_true", dest="git", default=False)
parser.add_option('--debug', action="store_true", dest="debug", default=False)


options, args = parser.parse_args()
local = False

xc3 = 'divoc'
wiki_url = 'https://di.c3voc.de/sessions-liste?do=export_xhtml#liste_der_self-organized_sessions'
main_schedule_url = 'https://talks.mrmcd.net/ptt/schedule/export/schedule.json'

additional_schedule_urls = [
]


# this list/map is required to sort the events in the schedule.xml in the correct way
# other rooms/assemblies are added at the end on demand.
rooms = {
    'stages': [
    ],
    'rooms': [
    ],
    'music': [
    ]
}

output_dir = "/srv/www/" + xc3
secondary_output_dir = "./" + xc3

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

if not os.path.exists("events"):
    os.mkdir("events")


from wikitable2schedule import fetch_schedule

def write(x):
    sys.stdout.write(x)
    sys.stdout.flush()

def generate_wiki_schedule(wiki_url: str, full_schedule: Schedule):

    wiki_schedule = fetch_schedule(wiki_url)

    write('Exporting... ')
    wiki_schedule.export('wiki')

    print('Wiki: done \n')
    return wiki_schedule


def main():
    global local, options

    full_schedule = Schedule.from_url(main_schedule_url)
    print('  version: ' + full_schedule.version())
    print('  contains {events_count} events, with local ids from {min_id} to {max_id}'.format(**full_schedule.stats.__dict__))



    # add addional rooms from this local config now, so they are in the correct order
    for key in rooms:
        full_schedule.add_rooms(rooms[key])


    previous_max_id = 0

    # add events from additional_schedule's to full_schedule
    for entry in additional_schedule_urls:
        try:
            #other_schedule = get_schedule(entry['name'], entry['url'])
            other_schedule = Schedule.from_url(entry['url'])

            if 'version' in other_schedule.schedule():
                full_schedule._schedule['schedule']['version'] += "; {}".format(entry['name'])
                print('  version: ' + other_schedule.version())
            else:
                print('  WARNING: schedule "{}" does not have a version number'.format(entry['name']))

            print('  contains {events_count} events, with local ids from {min_id} to {max_id}'.format(**other_schedule.stats.__dict__))
            id_offset = entry.get('id_offset')
            if not id_offset:
                id_offset = 0
            min_id = other_schedule.stats.min_id + id_offset
            max_id = other_schedule.stats.max_id + id_offset
            print('    after adding the offset, ids reach from {} to {}'.format(min_id, max_id))
            if previous_max_id >= min_id:
                 print('  WARNING: schedule "{}" has ID overlap with previous schedule'.format(entry['name']))
            previous_max_id = max_id

            if full_schedule.add_events_from(other_schedule, id_offset=id_offset, options=entry.get('options')):
                print('  success')

        except KeyboardInterrupt:
            exit()

        except Exception as e:
            print('  UNEXPECTED ERROR:' + str(sys.exc_info()[1]))
            if options.exit_when_exception_occours:
                raise e

    print('\nBuilding wiki schedule...')

    # wiki
    wiki_schedule = generate_wiki_schedule(wiki_url, full_schedule)

    full_schedule._schedule['schedule']['version'] += "; wiki"
    full_schedule.add_events_from(wiki_schedule)

    # write all events to one big schedule.json/xml
    write('\nExporting... ')
    full_schedule.export('everything')

    # write seperate file for each event, to get better git diffs
    #full_schedule.foreach_event(lambda event: event.export('events/'))
    #def export_event(event):
    #    with open("events/{}.json".format(event['guid']), "w") as fp:
    #        json.dump(event, fp, indent=2, cls=ScheduleEncoder)
    #
    #full_schedule.foreach_event(export_event)

    print('\nDone')
    print('  version: ' + full_schedule.version())

    print('\n  rooms of day 1: ')
    for room in full_schedule.day(1)['rooms']:
        print('   - ' + room)

    if not local or options.git:
        content_did_not_change = os.system('/usr/bin/env git diff -U0 --no-prefix | grep -e "^[+-]  " | grep -v version > /dev/null')

        def git(args):
            os.system('/usr/bin/env git {}'.format(args))

        if content_did_not_change:
            print('nothing relevant changed, reverting to previous state')
            git('reset --hard')
        else:
            git('add *.json *.xml events/*.json')
            git('commit -m "version {}"'.format(full_schedule.version()))
            git('push')

if __name__ == '__main__':
    main()
