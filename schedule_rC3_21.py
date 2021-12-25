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
from voc.tools import load_json, write
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
]

'''    {
    'name': 'rc3-channels',
    'url': 'https://pretalx.rc3.studio/rc3-channels-2020/schedule/export/schedule.json',
    'options': {
        'rewrite_id_from_question': 15,
        'room-map': {
            'ChaosTrawler Stubnitz/Gängeviertel Hamburg': 'ChaosTrawler'
        },
    }
} '''

additional_schedule_urls = channels

id_offsets = {
    # c3voc preatax schedule local ids's range from to till 500
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
    ]
}

output_dir = '/srv/www/' + xc3
secondary_output_dir = './' + xc3

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

if not os.path.exists('events'):
    os.mkdir('events')


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
    channel_schedule = export_stages_schedule(full_schedule)

    # write all events from non-frab to a own schedule.json/xml
    # def non_frab_filter(key):
    #    return not(key in frab_rooms)
    #export_filtered_schedule('non-frab', channel_schedule, non_frab_filter)


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
        content_did_not_change = os.system("/usr/bin/env git diff -U0 --no-prefix | grep -e '^[+-]  ' | grep -v version > /dev/null")

        if content_did_not_change:
            print('nothing relevant changed, reverting to previous state')
            git('reset --hard')
            exit(0)

        git('add *.json *.xml events/*.json')
        git('commit -m "version {}"'.format(full_schedule.version()))
        git('push')

        # update hub
        if False:
            print('\n== Updating rc3.world via API…')

            rc3hub.init(channels)
            repo = gitlib.Repo('.')
            changed_items = repo.index.diff('HEAD~1', 'events')
            for i in changed_items:
                write(i.change_type + ': ')
                try:
                    if i.change_type == 'D':
                        event_guid = os.path.splitext(os.path.basename(i.a_path))[0]
                        rc3hub.depublish_event(event_guid)
                    else:
                        event = load_json(i.a_path)
                        if event.get('origin') != 'rc3.world':
                            rc3hub.upsert_event(event)
                except Exception as e:
                    print(e)
                    if options.exit_when_exception_occours:
                        raise e
            print('\n\n')
            exit(2)


def git(args):
    os.system('/usr/bin/env git {}'.format(args))


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

    schedule.export('channels')
    return schedule


def export_filtered_schedule(output_name, parent_schedule, filter):
    write('\nExporting {} schedule... '.format(output_name))
    schedule = parent_schedule.copy(output_name)
    for day in schedule.days():
        room_keys = list(day['rooms'].keys())
        for room_key in room_keys:
            if not(filter(room_key)):
                del day['rooms'][room_key]

    print('\n  {}: '.format(output_name))
    for room in schedule.rooms():
        print('   - {}'.format(room))

    schedule.export(output_name)
    return schedule


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
        'Talk': 'Talk',
        'Vortrag': 'Talk',
        'lecture': 'Talk',
        'Beitrag': 'Talk',
        'Track': 'Talk',
        'Live on stage': 'Talk',
        'Recorded': 'Talk',
        '60 min Talk + 15 min Q&A': 'Talk',
        '30 min Short Talk + 10 min Q&A': 'Talk',

        # LIGHTNING TALK
        'Lightningtalk': 'Lightning Talk',
        'lightning_talk': 'Lightning Talk',
        'LightningTalk': 'Lightning Talk',
        'Lightning': 'Lightning Talk',

        # MEETUP
        'Meetup': 'Meetup',

        # OTHER
        'other': 'Other',
        'Other': 'Other',
        'Pausenfüllmaterial': 'Other',
        '': 'Other',

        # PODIUM
        'podium': 'Podium',

        # PERFORMANCE
        'Theater,': 'Performance',
        'performance': 'Performance',
        'Performance': 'Performance',

        # CONCERT
        'Konzert': 'Concert',
        'concert': 'Concert',

        # DJ Set
        'DJ Set': 'DJ Set',

        # WORKSHOP
        'Workshop': 'Workshop',

        # LIVE-PODCAST
        'Live-Podcast': 'Live-Podcast',
    }

    type = event.get('type').split()
    if not(type):
        event['type'] = 'Other'
    elif event.get('type') in type_mapping:
        event['type'] = type_mapping[event['type']]
    elif type[0] in type_mapping:
        event['type'] = type_mapping[type[0]]

    if event.get('language') is not None:
        event['language'] = event['language'].lower()

    if options.debug:
        print(event['type'])


if __name__ == '__main__':
    main()
