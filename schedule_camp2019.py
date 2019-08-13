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
from voc.schedule import Schedule, ScheduleEncoder

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
main_schedule_url = 'https://fahrplan.events.ccc.de/camp/{year}/Fahrplan/schedule.json'.format(year=year)
additional_schedule_urls = [
    { 'name': 'thm',     'url': 'https://talx.thm.cloud/thms/schedule/export/schedule.json',    'id_offset': 100},
#    { 'name': 'lounges',        'url': 'https://fahrplan.events.ccc.de/congress/2018/Lineup/schedule.json',             'id_offset': None},
#    { 'name': 'komona',         'url': 'https://talks.komona.org/35c3/schedule/export/schedule.json',                   'id_offset': 800},
#    { 'name': 'lightning',      'url': 'https://c3lt.de/camp2019/schedule/export/schedule.json',                            'id_offset': 3000}
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


from wiki2schedule import Wiki, process_wiki_events, load_sos_ids, store_sos_ids

def generate_wiki_schedule(wiki_url: str, full_schedule: Schedule):    
    data = Wiki(wiki_url)

    print("Wiki: Processing...")

    wiki_schedule = Schedule.empty_copy_of(full_schedule, 'Wiki')
    #wiki_schedule.add_rooms(rooms)    
    
    load_sos_ids()

    # process_wiki_events() fills global variables: out, wiki_schedule, workshop_schedule
    process_wiki_events(data, wiki_schedule)

    store_sos_ids()
    
    # write imported data from wiki to one merged file   
    #with open("sessions_complete.json", "w") as fp:
    #    json.dump(sessions_complete, fp, indent=4)

    wiki_schedule.export("wiki")
    
    print('Wiki: done')
    return wiki_schedule


def main():        
    #main_schedule = get_schedule('main_rooms', main_schedule_url)
    full_schedule = Schedule.from_url(main_schedule_url)

    # add addional rooms from this local config now, so they are in the correct order
    full_schedule.add_rooms(rooms)

    # add events from additional_schedule's to full_schedule
    for entry in additional_schedule_urls:
        try:
            #other_schedule = get_schedule(entry['name'], entry['url'])
            other_schedule = Schedule.from_url(entry['url'])
            
            if full_schedule.add_events_from(other_schedule, id_offset=entry.get('id_offset'), options=entry.get('options')):
                print("  success")

            if 'version' in other_schedule.schedule():
                full_schedule._schedule["schedule"]["version"] += " " + other_schedule.version()
            else:
                print('  WARNING: schedule "{}" does not have a version number'.format(entry['name']))

        except:
            print("  UNEXPECTED ERROR:" + str(sys.exc_info()[1]))

    print('Processing...')
    sys.stdout.write('  ')
    sys.stdout.flush()

    # wiki
    wiki_schedule = generate_wiki_schedule(wiki_url, full_schedule)


    # write all events to one big schedule.json/xml  
    #export_schedule("everything", full_schedule)
    full_schedule.export('everything')

    # write seperate file for each event, to get better git diffs
    #full_schedule.foreach_event(lambda event: event.export('events/'))
    def export_event(event):
        with open("events/{}.json".format(event['guid']), "w") as fp:
            json.dump(event, fp, indent=2, cls=ScheduleEncoder)

    full_schedule.foreach_event(export_event)

    
    print('Done')

    if not local or options.git:      
        content_did_not_change = os.system('/usr/bin/env git diff -U0 --no-prefix | grep -e "^[+-]  " | grep -v version > /dev/null')

        def git(args):
            os.system('/usr/bin/env git {}'.format(args))

        if content_did_not_change:
            print('nothing relevant changed, reverting to previous state')
            git('reset --hard')
        else:
            git('add *.json *.xml')
            git('commit -m "version {}"'.format(full_schedule.version()))
            git('push')

if __name__ == '__main__':
    main()
    

