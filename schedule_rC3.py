#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import requests
import json
import pytz
import os
import sys
import optparse
from voc.schedule import Schedule, ScheduleEncoder, Event

tz = pytz.timezone('Europe/Amsterdam')

parser = optparse.OptionParser()
parser.add_option('--online', action="store_true", dest="online", default=False)
parser.add_option('--show-assembly-warnings', action="store_true", dest="show_assembly_warnings", default=False)
parser.add_option('--fail', action="store_true", dest="exit_when_exception_occours", default=False)
parser.add_option('--git', action="store_true", dest="git", default=False)
parser.add_option('--debug', action="store_true", dest="debug", default=False)


options, args = parser.parse_args()
local = False
use_offline_frab_schedules = False
only_workshops = False

xc3 = "rC3"

main_schedule_url = 'https://fahrplan.events.ccc.de/rc3/2020/Fahrplan/schedule.json'

channels = requests \
    .get('https://c3voc.de/wiki/lib/exe/graphql2.php?query={channels{nodes{name:slug,url:schedule_url,schedule_room,room_guid}}}') \
    .json()['data']['channels']['nodes']

additional_schedule_urls = [
    { 
        'name': 'rc3-channels',       
        'url': 'https://pretalx.rc3.studio/rc3-channels-2020/schedule/export/schedule.json',
        'options': {
            'rewrite_id_from_question': 15
        }
    }
] + channels

id_offsets = {
    'wikipaka': 1000,
    'chaoszone': 1500
    # main schedule local ids's start at about 10.000
}


# this list/map is required to sort the events in the schedule.xml in the correct way
# other rooms/assemblies are added at the end on demand.
rooms = {
    'channels': [
        'restrealitaet',
        # channels with video recordings/livestream – same order as streaming website
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

def write(x):
    sys.stdout.write(x)
    sys.stdout.flush()


def main():
    try:
        full_schedule = Schedule.from_url(main_schedule_url)
        print('  version: ' + full_schedule.version())
        #print('  contains {events_count} events, with local ids from {min_id} to {max_id}'.format(**full_schedule.stats.__dict__))
    except:
        full_schedule = Schedule.from_XC3_template(None, 37, 27, 4)
        conference = full_schedule.conference()
        conference['acronym'] = 'rC3'
        conference['title'] = 'Remote Chaos Experience'

    loaded_schedules = {
        main_schedule_url: True,
        'https://frab.cccv.de/': True
    }

    # add addional rooms from this local config now, so they are in the correct order
    for key in rooms:
        full_schedule.add_rooms(rooms[key])


    previous_max_id = 0

    # add events from additional_schedule's to full_schedule
    for entry in additional_schedule_urls:
        try:
            print('\n== Channel ' + entry['name'])
            url = entry['url'].replace('schedule.xml', 'schedule.json')
            if entry.get('room_guid'):
                full_schedule._room_ids[entry['schedule_room'] or entry['name']] = entry['room_guid']
            if not url:
                print('  has no schedule_url yet – ignoring')
                continue
            if url in loaded_schedules:
                print('  schedule ' + url + ' was already loaded – ignoring')
                continue
            other_schedule = Schedule.from_url(url)
            loaded_schedules[url] = True

            if 'version' in other_schedule.schedule():
                full_schedule._schedule['schedule']['version'] += "; {}".format(entry['name'])
                print('  version: ' + other_schedule.version())
            else:
                print('  WARNING: schedule "{}" does not have a version number'.format(entry['name']))

            print('  contains {events_count} events, with local ids from {min_id} to {max_id}'.format(**other_schedule.stats.__dict__))
            id_offset = entry.get('id_offset') or id_offsets.get(entry['name']) or 0 
            min_id = other_schedule.stats.min_id + id_offset
            max_id = other_schedule.stats.max_id + id_offset
            print('    after adding the offset, ids reach from {} to {}'.format(min_id, max_id))
            
            # TODO improve error message and check actual intervals
            # if previous_max_id >= min_id:
            #    print('  WARNING: schedule "{}" might have ID overlap with other schedules'.format(entry['name']))
            
            if full_schedule.add_events_from(other_schedule, id_offset=id_offset, options=entry.get('options')):
                print('  success')

        except KeyboardInterrupt:
            exit()

        except Exception as e:
            print('  UNEXPECTED ERROR:' + str(sys.exc_info()[1]))
            if options.exit_when_exception_occours:
                raise e

    # remove breaks from lightning talk schedule import
    # full_schedule.remove_event(guid='bca1ec84-e62d-528a-b254-68401ece6c7c')
    full_schedule.foreach_event(harmonize_event_type)


    # write all events from the channels to a own schedule.json/xml
    write('\nExporting channels... ')
    channels = full_schedule.copy('Channels')
    for day in channels._schedule['schedule']['conference']['days']:
        i = 0
        room_keys = list(day['rooms'].keys())
        for room_key in room_keys:
            if ('Workshop' in room_key or 'Meetup' in room_key) and \
              not(i < 4 or room_key in rooms['channels']):
                del day['rooms'][room_key]
            i += 1

    print('\n  channels: ')
    for room in channels.rooms():
        print('   - ' + room)

    channels.export('channels')
    del channels

    full_schedule.foreach_day_room(remove_too_early_events)

    # write all events to one big schedule.json/xml
    write('\nExporting... ')
    full_schedule.export('everything')

    # write seperate file for each event, to get better git diffs
    def export_event(event):
        with open("events/{}.json".format(event['guid']), "w") as fp:
            json.dump({
                **event,
                'room_guid': full_schedule._room_ids.get(event['room'], None)
            }, fp, indent=2, cls=ScheduleEncoder)

    full_schedule.foreach_event(export_event)

    print('\nDone')
    print('  version: ' + full_schedule.version())

    print('\n  rooms: ')
    for room in full_schedule.rooms():
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

# remove talks starting before 9 am
def remove_too_early_events(room):
    for event in room:
        start_time = Event(event).start
        if start_time.hour > 4 and start_time.hour < 9:
            print('removing {} from full schedule, as it takes place at {} which is too early in the morning'.format(event['title'], start_time.strftime('%H:%M')))
            room.remove(event)
        else:
            break

# harmonize event types 
def harmonize_event_type(event):
    type_mapping = {

        # TALKS
        "Talk": "Talk",
        "Talk 20 Minuten + 5 Minuten Fragen": "Talk",
        "Talk 30 min + 10min Q&A": "Talk",
        "Talk 45 Minuten + 10 Minuten für Fragen": "Talk",
        "Talk 45+10 Min": "Talk",
        "Talk 20+5 Min": "Talk",
        "Talk 60min + 20min Q&A": "Talk",
        "Vortrag": "Talk",
        "lecture": "Talk",
        "Beitrag": "Talk",

        # LIGHTNING TALK
        "lightning_talk": "Lightning Talk",
        "LightningTalk 15min 10min Q&A": "Lightning Talk",

        # MEETUP
        "Meetup": "Meetup",

        # OTHER
        "other": "Other",
        "Other": "Other",
        "": "Other",

        # PODIUM
        "podium": "Podium",

        # PERFORMANCE
        "Theater, Performance, oder irgendwas ganz anderes formatsprengendes": "Performance",
        "performance": "Performance",
        "Performance": "Performance",
        "Performance 60min": "Performance",

        # CONCERT
        "Konzert": "Concert",
        "concert": "Concert",            

        # DJ Set
        "DJ Set": "DJ Set",

        # WORKSHOP
        "Workshop": "Workshop",
        "Workshop 110min": "Workshop",
        "Workshop 60 Min": "Workshop",

        # LIVE-PODCAST
        "Live-Podcast": "Live-Podcast",
    }
    if event['type'] in type_mapping:
        event['type'] = type_mapping[event['type']]

if __name__ == '__main__':
    main()
