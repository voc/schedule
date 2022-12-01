#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import requests
import json
import pytz
import os
import sys
import optparse
import git as gitlib

from voc.schedule import Schedule, ScheduleEncoder, Event
from voc.tools import commit_changes_if_something_relevant_changed, ensure_folders_exist, git, harmonize_event_type, load_json, write
from voc import rc3hub


tz = pytz.timezone('Europe/Amsterdam')

parser = optparse.OptionParser()
parser.add_option('--online', action='store_true', dest='online', default=False)
parser.add_option('--show-assembly-warnings', action='store_true', dest='show_assembly_warnings', default=False)
parser.add_option('--fail', action='store_true', dest='exit_when_exception_occours', default=False)
parser.add_option('--stats', action='store_true', dest='only_stats', default=False)
parser.add_option('--git', action='store_true', dest='git', default=False)
parser.add_option('--debug', action='store_true', dest='debug', default=False)


options, args = parser.parse_args()
local = False
use_offline_frab_schedules = False
only_workshops = False

# channels = requests \
#    .get('https://c3voc.de/wiki/lib/exe/graphql2.php?query={channels{nodes{name:slug,url:schedule_url,schedule_room,room_guid,prefix}}}') \
#    .json()['data']['channels']['nodes']

xc3 = 'rC3_21'
channels = [
    {
        'url': 'https://pretalx.c3voc.de/rc3-2021-fem/schedule/export/schedule.json', 
        'name': 'FeM',
        'room_guid': '69371c99-1f93-4d01-8ea6-65b0e748b9e0',
        'stage': 'FeM Channel'
    },
    {
        'url': 'https://pretalx.c3voc.de/rc3-2021-cbase/schedule/export/schedule.json',
        'name': 'c-base',
        'room_guid': '5cfed623-26cc-4ac4-a4b2-0653195ddb4a',
        'stage': 'c-base'
    },
    {
        'url': 'https://pretalx.c3voc.de/rc3-2021-cwtv/schedule/export/schedule.json',
        'name': 'CWTV',
        'room_guid': '01a11ad1-38e2-464d-b0bb-de6a85534ed4',
        'stage': 'Chaos-West TV'
    },
    {
        'url': 'https://pretalx.c3voc.de/rc3-2021-chaosstudiohamburg/schedule/export/schedule.json',
        'name': 'Chaosstudio Hamburg',
        'room_guid': 'a4475839-786e-451b-aaa4-b37ed830ab2f',
        'stage': 'Chaosstudio Hamburg'
    },
    {
        'url': 'https://pretalx.c3voc.de/rc3-2021-chaoszone/schedule/export/schedule.json',
        'name': 'ChaosZone TV',
        'room_guid': 'e72d07ac-75b2-4b93-8f05-4bc7fe6e7e96',
        'stage': 'ChaosZone TV'
    },
    {
        'url': 'https://pretalx.c3voc.de/rc3-2021-r3s/schedule/export/schedule.json',
        'name': 'r3s',
        'room_guid': 'f91f4af4-b667-4705-9aab-5c280177bf49',
        'stage': 'r3s - Monheim/Rhein'
    },
    {
        'url': 'https://cfp.franconian.net/end-of-year-event-2021/schedule/export/schedule.json',
        'name': 'franconian.net',
        'options': {
            'overwrite_slug': True
        },
        'room_guid': '6e8bfc10-0670-412e-bbe9-7b9aa1dcd714',
        'stage': 'franconian.net'
    },
    {
        'url': 'https://pretalx.c3voc.de/rc3-2021-hacc-a-f/schedule/export/schedule.json',
        'name': 'about:future / hacc',
        'room_guid': 'c2789542-5d1a-41a7-a934-119f762fbdb0',
        'stage': 'about:future stage'
    },
    {
        'url': 'https://pretalx.c3voc.de/rc3-2021-sendezentrum/schedule/export/schedule.json',
        'name': 'Sendezentrum',
        'room_guid': 'd1915b0a-6d9d-47f0-b9e8-3c00ab62e2fe',
        'stage': 'Sendezentrum Bühne'
    },
    {
        'url': 'https://pretalx.c3voc.de/rc3-2021-haecksen/schedule/export/schedule.json',
        'name': 'haecksen',
        'room_guid': '6246d4db-85df-47de-b4ef-1edb76b5bd7b',
        'stage': 'Haecksen Stream'
    },
    {
        'url': 'https://pretalx.c3voc.de/rc3-2021-gehacktes-from-hell/schedule/export/schedule.json',
        'name': 'hell',
        'room_guid': 'e5d65c11-3c4e-418c-aebe-4fc7a655176b',
        'stage': 'Bierscheune'
    },
    {
        'url': 'https://pretalx.c3voc.de/rc3-2021-xhain/schedule/export/schedule.json',
        'name': 'xHain',
        'room_guid': '32277bdb-ae00-4cfb-81f1-e9ef36aee72d',
        'stage': 'Lichtung'
    },
    {
        'url': 'https://pretalx.c3voc.de/rc3-2021-lounge/schedule/export/schedule.json',
        'name': 'lounge',
        'room_guid': '3fa26587-25ef-4b6e-9d16-e9e16bc26854',
        'stage': 'rC3 Lounge'
    },
    {
        'url': 'https://pretalx.c3voc.de/rc3-2021-chill-lounge/schedule/export/schedule.json',
        'name': 'abchillgleis',
        'room_guid': '94170a45-363b-40e3-9157-c044f1c56309',
        'stage': 'Abchillgleis'
    },
]

additional_schedule_urls = channels

targets = [
    'filesystem',
    'voctoimport',
    # 'rc3hub'
]

id_offsets = {
    # franconian local talk ids are <100, but speaker integer ids might collide 
    #   when 10 additional speakers are created there
    # c3voc preatax schedule local ids's range from 120 to till >500
}


# this list/map is required to sort the events in the schedule.xml in the correct way
# other rooms/assemblies are added at the end on demand.
rooms = {
    'channels': [
        # channels with video recordings/livestream – same order as streaming website
        'Chaos-West TV',
        'Chaosstudio Hamburg',
        'ChaosZone TV',
        'c-base',
        'r3s - Monheim/Rhein',
        'FeM Channel',
        'franconian.net',
        'about:future stage',
        'Sendezentrum Bühne',
        'Haecksen Stream',
        'Lichtung',
        'Bierscheune',
    ],
    'rooms': [
    ],
    'music': [
        'rC3 Lounge',
        'Abchillgleis',
    ]
}

output_dir = '/srv/www/' + xc3
secondary_output_dir = './' + xc3

ensure_folders_exist(output_dir, secondary_output_dir)
os.chdir(output_dir)


def main():
    #try:
    #    full_schedule = Schedule.from_url(main_schedule_url)
    #    print('  version: ' + full_schedule.version())
    #    #print('  contains {events_count} events, with local ids from {min_id} to {max_id}'.format(**full_schedule.stats.__dict__))
    #except:
    full_schedule = Schedule.from_XC3_template(None, 38, 27, 4)
    conference = full_schedule.conference()
    conference['acronym'] = 'rc3-2021'
    conference['title'] = 'rC3 NOWHERE'

    loaded_schedules = {}

    # add addional rooms from this local config now, so they are in the correct order
    for key in rooms:
        full_schedule.add_rooms(rooms[key])

    # add room guid's to schedule class
    for entry in channels:
        if entry.get('room_guid'):
            full_schedule._room_ids[entry['stage'] or entry['name']] = entry['room_guid']


    # add events from additional_schedule's to full_schedule
    for entry in additional_schedule_urls:
        try:
            print('\n== Channel ' + entry['name'])
            url = entry['url'].replace('schedule.xml', 'schedule.json')
            if not url:
                print('  has no schedule_url yet – ignoring')
                continue
            if url in loaded_schedules:
                print('  schedule ' + url + ' was already loaded – ignoring')
                continue
            other_schedule = Schedule.from_url(url)
            loaded_schedules[url] = True

            if 'version' in other_schedule.schedule():
                full_schedule._schedule['schedule']['version'] += '; {}'.format(entry['name'])
                print('  version: ' + other_schedule.version())
            else:
                print('  WARNING: schedule "{}" does not have a version number'.format(entry['name']))

            try:
                print('  contains {events_count} events, with local ids from {min_id} to {max_id}'.format(**other_schedule.stats.__dict__))
                print('    local person ids from {person_min_id} to {person_max_id}'.format(**other_schedule.stats.__dict__))
                print('    rooms: {}'.format(', '.join(other_schedule.rooms())))

            except:
                pass

            id_offset = entry.get('id_offset') or id_offsets.get(entry['name']) or 0 

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

    # remove breaks from lightning talk schedule import
    # full_schedule.remove_event(guid='bca1ec84-e62d-528a-b254-68401ece6c7c')

    if options.only_stats:
        exit()

    full_schedule.foreach_event(harmonize_event_type)

    # write all events from the channels to a own schedule.json/xml
    export_stages_schedule(full_schedule)
    export_streams_schedule(full_schedule)

    # to get proper a state, we first have to remove all event files from the previous run
    if not local or options.git:
        git('rm events/*')

    # write seperate file for each event, to get better git diffs
    def export_event(event: Event):
        origin_system = None
        if isinstance(event, Event):
            origin_system = event.origin.origin_system

        with open('events/{}.json'.format(event['guid']), 'w') as fp:
            json.dump({
                **event,
                'room_id': full_schedule._room_ids.get(event['room'], None),
                'origin': origin_system or None,
            }, fp, indent=2, cls=ScheduleEncoder)

    full_schedule.foreach_event(export_event)

    # write all events to one big schedule.json/xml
    write('\nExporting... ')
    full_schedule.export('everything')

    # expose metadata to own file
    with open('meta.json', 'w') as fp:
        json.dump({
            'data': {
                'version': full_schedule.version(),
                'source_urls': list(loaded_schedules.keys()),
                'rooms': [{
                    'guid': full_schedule._room_ids.get(room, None),
                    'schedule_name': room
                } for room in full_schedule.rooms()],
                'channels': channels
            },
        }, fp, indent=2, cls=ScheduleEncoder)

    print('\nDone')
    print('  version: ' + full_schedule.version())

    print('\n  rooms: ')
    for room in full_schedule.rooms():
        print('   - ' + room)
    print()

    if not local or options.git:
        commit_changes_if_something_relevant_changed(full_schedule)


def export_stages_schedule(full_schedule):
    write('\nExporting channels... ')
    schedule = full_schedule.copy('Channels')
    for day in schedule.days():
        i = 0
        room_keys = list(day['rooms'].keys())
        for room_key in room_keys:
            if not(room_key in rooms['channels']):
                del day['rooms'][room_key]
            i += 1

    print('\n  channels: ')
    for room in schedule.rooms():
        print('   - {} {}'.format(full_schedule._room_ids.get(room), room))

    schedule._schedule['schedule']['version'] = schedule.version().split(';')[0]
    schedule.export('channels')
    return schedule


def export_streams_schedule(full_schedule):
    write('\nExporting streams... ')
    schedule = full_schedule.copy('Streams')
    for day in schedule.days():
        i = 0
        room_keys = list(day['rooms'].keys())
        for room_key in room_keys:
            if not(room_key in rooms['channels']) and not(room_key in rooms['music']):
                del day['rooms'][room_key]
            i += 1

    schedule._schedule['schedule']['version'] = schedule.version().split(';')[0]
    schedule.export('streams')
    return schedule


if __name__ == '__main__':
    main()
