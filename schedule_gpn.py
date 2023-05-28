#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

#import requests
import json
import requests
import pytz
import os
import sys
import optparse
# import git as gitlib

from voc.schedule import Schedule, ScheduleEncoder, Event
from voc.tools import commit_changes_if_something_relevant_changed, ensure_folders_exist, export_filtered_schedule, git, harmonize_event_type, load_json, write
from voc import rc3hub


tz = pytz.timezone('Europe/Amsterdam')

parser = optparse.OptionParser()
parser.add_option('--online', action="store_true", dest="online", default=False)
parser.add_option('--show-assembly-warnings', action="store_true", dest="show_assembly_warnings", default=False)
parser.add_option('--fail', action="store_true", dest="exit_when_exception_occours", default=False)
parser.add_option('--git', action="store_true", dest="git", default=False)
parser.add_option('--debug', action="store_true", dest="debug", default=False)


options, args = parser.parse_args()
local = True
use_offline_frab_schedules = False
only_workshops = False

xc3 = "GPN21"

main_schedule_url = 'https://cfp.gulas.ch/gpn21/schedule/export/schedule.json'

additional_schedule_urls = [
    {
        'name': 'GPN21 Lounge',
        'url': 'https://cfp.gulas.ch/gpn21-lounge/schedule/export/schedule.json',
        'id_offset': 1000,
        'slug': 'lounge',
    }
]


id_offsets = {
}


# this list/map is required to sort the events in the schedule.xml in the correct way
# other rooms/assemblies are added at the end on demand.
rooms = {
    'channels': [
        # channels with video recordings/livestream – same order as streaming website
    ],
    'rooms': [
    ],
    'music': [
    ]
}

output_dir = "./out/"+ xc3
secondary_output_dir = "./out/" + xc3
# expand relative out_dir paths
if not output_dir.startswith('/'):
    output_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), output_dir)
if not secondary_output_dir.startswith('/'):
    secondary_output_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), secondary_output_dir)

if len(sys.argv) == 2:
    output_dir = sys.argv[1]

ensure_folders_exist(output_dir, secondary_output_dir)
os.chdir(output_dir)


def main():

    full_schedule = Schedule.from_url(main_schedule_url)
    print('  version: ' + full_schedule.version())
    print('  contains {events_count} events, with local ids from {min_id} to {max_id}'.format(**full_schedule.stats.__dict__))


    # append lounge url
    for entry in additional_schedule_urls:
        try:
            print('\n== SUB Event  ' + entry['name'])
            url = entry['url'].replace('schedule.xml', 'schedule.json')
            if not url:
                print('  has no schedule_url yet – ignoring')
                continue
 
            other_schedule = Schedule.from_url(url)

            id_offset = entry.get('id_offset') or id_offsets.get(entry['name']) or 0

            other_schedule["version"] = entry['slug']+other_schedule["version"] 

            if full_schedule.add_events_from(other_schedule, id_offset=id_offset, options={
                **(entry.get('options') or {}),
                'prefix_person_ids': entry.get('prefix')
            }):
                print('  success')

        except KeyboardInterrupt:
            exit()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                print('  not yet available (404)')
            else:
                print('  HTTP ERROR: ' + str(e))
                if options.exit_when_exception_occours:
                    raise e
        except Exception as e:
            print('  UNEXPECTED ERROR:' + str(sys.exc_info()[1]))
            if options.exit_when_exception_occours:
                raise e

    

    #full_schedule.foreach_event(harmonize_event_type)
    #
    # write all events to one big schedule.json/xml
    write('\nExporting... ')
    full_schedule.export('everything')

    print('\nDone')
    print('  version: ' + full_schedule.version())

    print('\n  rooms: ')
    for room in full_schedule.rooms():
        print('   - ' + room)
    print()

if __name__ == '__main__':
    main()
