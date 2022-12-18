#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

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


congress_nr = 36
year = str(1983 + congress_nr)
xc3 = "{x}C3".format(x=congress_nr)

wiki_url = 'https://events.ccc.de/congress/{year}/wiki'.format(year=year)
main_schedule_url = 'http://fahrplan.events.ccc.de/congress/{year}/Fahrplan/schedule.json'.format(year=year)

additional_schedule_urls = [
    { 'name': 'lounges',        'url': 'https://fahrplan.events.ccc.de/congress/2019/Lineup/schedule.json',             'id_offset': None},
    { 'name': 'chaos-west',     'url': 'https://fahrplan.chaos-west.de/36c3/schedule/export/schedule.json',             'id_offset': 100},
    { 'name': 'open-infra',     'url': 'https://talks.oio.social/36c3-oio/schedule/export/schedule.json',               'id_offset': 200},
    { 'name': 'wikipaka',       'url': 'https://cfp.verschwoerhaus.de/36c3/schedule/export/schedule.json',              'id_offset': 500},
    { 'name': 'chaoszone',      'url': 'https://cfp.chaoszone.cz/36c3/schedule/export/schedule.json',                   'id_offset': 700},
    { 'name': 'komona',         'url': 'https://talks.komona.org/36c3/schedule/export/schedule.json',                   'id_offset': 800, 
      'options': { 'room-prefix': '1Komona '}
    },
    { 'name': 'sendezentrum',   'url': 'https://fahrplan.das-sendezentrum.de/36c3/schedule/export/schedule.json',       'id_offset': 800},
    # generated wiki event id's start from 1000 
    { 'name': 'lightning',      'url': 'https://c3lt.de/36c3/schedule/export/schedule.json',                            'id_offset': 3000},
    { 'name': 'art-play',       'url': 'https://stage.artesmobiles.art/36c3/schedule/export/schedule.json',             'id_offset': 4100},
    { 'name': 'cdc',            'url': 'https://frab.riat.at/en/36C3/public/schedule.json',                             'id_offset': 4200},
    # main schedule local ids's start at about 10.000
]


# this list/map is required to sort the events in the schedule.xml in the correct way
# other rooms/assemblies are added at the end on demand.
rooms = {
    'stages': [
        # Stages with video recordings/livestream – same order as streaming website
        "Chaos-West Bühne",
        "OIO Stage",
        "DLF- und Podcast-Bühne",
        "WikiPaka WG: Esszimmer",
    ],
    'rooms': [
        # SOS rooms
        "Lecture room 11",
        "Lecture room 12",
        "Seminar room 14-15",
        "Seminar room 13",
        "Lecture room M1",
        "Lecture room M2",
        "Lecture room M3",
    ],
    'music': [
        "Discotheque Nouveauancien",
        "Uptown",
        "Furo no ba",
        "Monipilami",
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


from wiki2schedule import Wiki, process_wiki_events, load_sos_ids, store_sos_ids

def write(x):
    sys.stdout.write(x)
    sys.stdout.flush()

def generate_wiki_schedule(wiki_url: str, full_schedule: Schedule):
    data = Wiki(wiki_url)

    write('Wiki: Processing...')

    wiki_schedule = Schedule.empty_copy_of(full_schedule, 'Wiki', start_hour = 9)
    wiki_schedule.add_rooms(rooms)

    load_sos_ids()

    # process_wiki_events() fills global variables: out, wiki_schedule, workshop_schedule
    process_wiki_events(data, wiki_schedule, timestamp_offset=-3600, options=options)
    store_sos_ids()

    write('Exporting... ')
    wiki_schedule.export('wiki')

    print('Wiki: done \n')
    return wiki_schedule


def main():
    #main_schedule = get_schedule('main_rooms', main_schedule_url)
    try:
        full_schedule = Schedule.from_url(main_schedule_url)
    except:
        full_schedule = Schedule.from_XC3_template(None, congress_nr, 27, 4)
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

    # remove breaks from lightning talk schedule import
    full_schedule.remove_event(guid='bca1ec84-e62d-528a-b254-68401ece6c7c')
    full_schedule.remove_event(guid='cda64c9e-b230-589a-ace0-6beca2693eff')
    full_schedule.remove_event(guid='f33dd7b7-99d6-574b-9282-26986b5a0ea0')


    # write all events from the stages to a own schedule.json/xml
    write('\nExporting main stages... ')
    stages = full_schedule.copy('Stages')
    for day in stages._schedule['schedule']['conference']['days']:
        i = 0
        room_keys = list(day['rooms'].keys())
        for room_key in room_keys:
            if not( i < 5 or room_key in rooms['stages'] or 'Stage' in room_key or 'Bühne' in room_key):
                del day['rooms'][room_key]
            i += 1

    print('\n  stages of day 1: ')
    for room in stages.day(1)['rooms']:
        print('   - ' + room)


    stages.export('stages')
    del stages

    print('\nBuilding wiki schedule...')

    # wiki
    wiki_schedule = generate_wiki_schedule(wiki_url, full_schedule)

    full_schedule['version'] += "; wiki"
    full_schedule.add_events_from(wiki_schedule)
    # remove rooms from wiki import, which we already have in more detail as pretalx rooms
    full_schedule.remove_room('Assembly:Art-and-Play')
    full_schedule.remove_room('Assembly:ChaosZone')
    full_schedule.remove_room('Assembly:WikipakaWG')

    # remove lighthing talk slot to fill with individual small events per lighthing talk
    #full_schedule.remove_event(id=10380)

    # remove talks starting before 9 am
    def remove_too_early_events(room):
        for event in room:
            start_time = Event(event).start
            if start_time.hour > 4 and start_time.hour < 9:
                print('removing {} from full schedule, as it takes place at {} which is too early in the morning'.format(event['title'], start_time.strftime('%H:%M')))
                room.remove(event)
            else:
                break
    full_schedule.foreach_day_room(remove_too_early_events)
        

    # write all events to one big schedule.json/xml
    write('\nExporting... ')
    full_schedule.export('everything')

    # write seperate file for each event, to get better git diffs
    #full_schedule.foreach_event(lambda event: event.export('events/'))
    def export_event(event):
        with open("events/{}.json".format(event['guid']), "w") as fp:
            json.dump(event, fp, indent=2, cls=ScheduleEncoder)

    full_schedule.foreach_event(export_event)

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
