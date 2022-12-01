#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import requests
import json
import pytz
import os
import sys
import optparse
import git as gitlib
from urllib.parse import urlparse

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

xc3 = 'jev22'
# source pad https://lab.nrw/hedgedoc/_hV5kXt9TKuiV0DVsdIwgg
conferences = [
    {
        'url': 'https://pretalx.c3voc.de/hip-berlin-2022/schedule/export/schedule.json',
        'name': 'Hacking in Parallel',  # (27.–30.)
        'location': 'Berlin, c-base',
        'links': ['https://wiki.hip-berlin.de/']
    },
    {
        'url': 'TBD',
        'name': 'dezentrale Chaos-Culture',  # (27.–28.)
        'location': 'Bielefeld, Digitalcourage',
        'links': ['https://digitalcourage.de/']
    },
    {
        'url': 'https://pretalx.c3voc.de/hacking-in-hell-2022/schedule/export/schedule.json',
        'name': 'Hellarious: Hacking in Hell',
        'location': 'Brandenburg, Alte Hölle',
        'links': ['https://alte-hoelle.de/']
    },
    {
        'url': 'https://pretalx.c3voc.de/xrelog-2022/schedule/export/schedule.json',
        'name': 'xrelog22: Independent Multiverses',  # (28.–30.)
        'location': 'Hamburg, FTZ/HAW',
        'links': [
            'https://events.ccc.de/2022/11/13/xrelog22-cfp/',
            'https://matrix.to/#/#xrevent:matrix.org'
        ]
    },
    {
        'url': 'TBD',
        'name': 'localverse2022',  # (27.–30.)
        'location': 'Leipzig',
        'links': [
            'https://dezentrale.space/posts/2022/11/localverse2022-call-for-participation-20221118/', 
            'https://matrix.to/#/#localverse2022:chat.dezentrale.space'
        ]
    },
    {
        'url': 'https://forum.freiraeumen.jetzt/freiraumforum/schedule/export/schedule.json',
        'name': 'Forum für Freiräume - Gib Uns Mehr!',  # (26.–31.)
        'location': 'München',
        'links': ['https://events.ccc.de/2022/11/18/ff22-cfp/'],
    },
    {
        'url': 'https://cfp.ccc-p.org/rtc22/schedule/export/schedule.json',
        'name': 'Reconnect To Chaos!',  # (27.–30.)
        'location': 'Potsdam, Chaostreff',
        'links': ['https://www.ccc-p.org/rtc22/']
    },
    {
        'url': 'https://pretalx.c3voc.de/fire-shonks-2022/schedule/export/schedule.json',
        'name': 'FireShonks',  # (27.–30.)
        'location': 'Remote & Wülfrath',
        'links': [
            'https://events.ccc.de/2022/10/27/fireshonks-cfp/',
            'https://events.haecksen.org/fireshonks/'
        ]
    },
    {
        # TODO: Add iCal Support?
        #  webcals://ramac.mudbyte.de/remote.php/dav/public-calendars/YTtwyZcXsmZDfSoo/?export
        'name': 'ChilyConChaos',  # (28.–30.)
        'location': 'Gießen/Wetzlar',
        'links': ['https://chilyconchaos.de/']
    },
    {
        'url': 'https://talks.w.icmp.camp/schedule/export/schedule.json',
        'slug': 'wicmp1',
        'name': 'Wintergalaktische Club Mate Party',  # (27.–30.)
        'location': "Erlangen, Bits'n'Bugs + ZAM",
        'links': ['https://w.icmp.camp']
    }
]

additional_schedule_urls = conferences

targets = [
    'filesystem',
    # 'voctoimport',
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
    except Exception:
        print('Please create directory named {} if you want to run in local mode'.format(secondary_output_dir))
        exit(-1)
os.chdir(output_dir)

if not os.path.exists('events'):
    os.mkdir('events')

headers = {'Authorization': 'Token ' + os.getenv('PRETALX_TOKEN', ''), 'Content-Type': 'application/json'}


def main():
    #try:
    #    full_schedule = Schedule.from_url(main_schedule_url)
    #    print('  version: ' + full_schedule.version())
    #    #print('  contains {events_count} events, with local ids from {min_id} to {max_id}'.format(**full_schedule.stats.__dict__))
    #except:
    full_schedule = Schedule.from_XC3_template(None, 39, 27, 4)
    conference = full_schedule.conference()
    conference['acronym'] = 'jev22'
    conference['title'] = 'Dezentrale Jahresendveranstaltungen'

    loaded_schedules = {}

    # add addional rooms from this local config now, so they are in the correct order
    for key in rooms:
        full_schedule.add_rooms(rooms[key])

    # add room guid's to schedule class
    for entry in conferences:
        if entry.get('room_guid'):
            full_schedule._room_ids[entry['stage'] or entry['name']] = entry['room_guid']

    # add events from additional_schedule's to full_schedule
    for entry in additional_schedule_urls:
        try:
            print(f"\n== Conference `{entry['name']}` ({entry['location']})")
            url = entry.get('url', '').replace('schedule.xml', 'schedule.json')
            if not url or url == 'TBD':
                print('  has no schedule_url yet – ignoring')
                continue
            if url in loaded_schedules:
                print('  schedule ' + url + ' was already loaded – ignoring')
                continue
            
            # https://pretalx.c3voc.de/hip-berlin-2022/schedule/export/schedule.json
            r = urlparse(url.replace('/schedule/export/schedule.json', ''))
            slug = entry.get('slug', os.path.basename(r.path))
            # /api/events/hip-berlin-2022/rooms/
            entry['api_url'] = f"{r.scheme}://{r.netloc}{os.path.dirname(r.path)}/api/events/{slug}"

            entry['meta'] = requests.get(entry['api_url'], timeout=1).json()
            entry['rooms'] = requests.get(entry['api_url'] + '/rooms', timeout=1, headers=headers).json().get('results')

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

            except Exception:
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
    #  export_stages_schedule(full_schedule)
    #  export_streams_schedule(full_schedule)

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
                'conferences': conferences
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

            rc3hub.init(conferences)
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


def export_filtered_schedule(output_name, parent_schedule, filter):
    write('\nExporting {} schedule... '.format(output_name))
    schedule = parent_schedule.copy(output_name)
    for day in schedule.days():
        room_keys = list(day['rooms'].keys())
        for room_key in room_keys:
            if not (filter(room_key)):
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
        'Lightning-Talk': 'Lightning Talk',
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
    if not (type):
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
