#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import os
from typing import List
import requests
import json
import pytz
import sys
import optparse
from datetime import datetime

from voc import (
    GenericConference,
    PretalxConference,
    WebcalConference,
    Event,
    Schedule,
    ScheduleEncoder,
    ScheduleException,
    Room,
    Logger,
)

from voc.c3data import C3data
from git import Repo

# from voc.schedule import set_validator_filter
from voc.tools import (
    commit_changes_if_something_relevant_changed,
    git,
    harmonize_event_type,
    write,
    ensure_folders_exist,
)

tz = pytz.timezone("Europe/Amsterdam")
local = False

parser = optparse.OptionParser()
parser.add_option("--online", action="store_true", dest="online", default=False)
parser.add_option(
    "--fail", action="store_true", dest="exit_when_exception_occours", default=local
)
parser.add_option("--stats", action="store_true", dest="only_stats", default=False)
parser.add_option("--git", action="store_true", dest="git", default=False)
parser.add_option("--debug", action="store_true", dest="debug", default=local)

log = Logger(__name__)
options, args = parser.parse_args()

xc3 = "camp2023"

conferences: List[GenericConference] = [
    #GenericConference(
    #    url="https://events.ccc.de/camp/2023/hub/api/c/camp23/schedule.json",
    #    data={
    #        "name": "hub"
    #    }
    #),
    PretalxConference(
        url="https://pretalx.c3voc.de/camp2023",
        data={
            "name": "channels"
        }
    ),
    PretalxConference(
        url="https://fahrplan.alpaka.space/camp-2023",
        data={
            "name": "jugendvillage",
            "location":  "Jugend Village",
        },
    ),
]
'''
    GenericConference(
        url="https://data.jtbx.de/jev22_ccl/schedule.json",
        options={
            "track": "Curious Community Labs",
            "id_offsets": -200
        },
    ),
    GenericConference(
        url="https://laborluxeria.github.io/winterchaos2022/schedule.json",
        # https://github.com/laborluxeria/winterchaos2022/tree/main/_sessions – michi
        data={
            "name": "Winterchaos",
            "location": "Luzern, CH",
            "description": "Ein gemütlicher Jahresabschluss des LABOR Luzern und der LuXeria Luzern mit lokalen Vorträgen und Workshops.",
            "geolocation": [47.0360555, 8.2799098],
            "links": [
                "https://laborluxeria.github.io/winterchaos2022/schedule/",
                "https://laborluxeria.github.io/winterchaos2022/feed.xml",
            ],
            "osm_url": "https://www.openstreetmap.org/node/5365063316#v13"
        }
    ),
'''

targets = [
    "filesystem",
    "c3data",
    # "voctoimport",
    # "rc3hub"
]

id_offsets = {
}

# this list/map is required to sort the events in the schedule.xml in the correct way
# other rooms/assemblies are added at the end on demand.
rooms = {
    "channels": [
        # channels with video recordings/livestream – same order as streaming website,
        Room(name="Marktplatz",     stream="s1", guid="5b239f1d-06c8-4e7c-b824-25b6ee7360d1"),
        Room(name="Milliways",      stream="s2", guid="345ca97a-7eb6-459b-bc53-bc2a8bd5c3f1"),
        Room(name="Digitalcourage", stream="s3", guid="7c1ad02f-4d33-4d48-a5a3-0e6798a18d01"),
        Room(name="N:O:R:T:x",      stream="s4", guid="52f1a9fa-580e-4a32-bf20-4326902717aa"),
        Room(name="Bits & Bäume",   stream="s5", guid="f9b82a04-1354-4ee5-9df6-c71b6cde66ea"),
        Room(name="C3VOC.tv",       stream="s6", guid="a06db024-2ab8-49ce-940f-2814b5fb9740"),
        Room(name="Jugend Village", stream="s191", guid="e89b5a42-da11-4298-ac84-d20e777055c9"),
    ],
    "rooms": [
    ],
    "music": [
        # Room(name="UFO", guid="0a639330-e9ac-4d22-8dbc-3571ed8e9640"),
        # Room(name="Culture Club", guid="7fe8d330-843e-4f7f-a3c3-d502cab09140"),
        # Room(name="Chill Lagune am Herzbergstich", guid="8ad5b9c6-ea4f-4e43-b80e-4a1e3d46f13c"),
    ],
}

channels = {}
for c in rooms['channels']:
    channels[c.guid or c.name] = c

output_dir = "/srv/www/" + xc3
secondary_output_dir = "./" + xc3
if len(sys.argv) == 2:
    output_dir = sys.argv[1]

local = ensure_folders_exist(output_dir, secondary_output_dir)


def main():
    base_schedule = Schedule(
        conference={
            "acronym": "camp2023",
            "title": "Chaos Communication Camp 2023",
            "start": "2023-08-15",
            "end": "2023-08-20",
            "daysCount": 6,
            "timeslot_duration": "00:15",
            "time_zone_name": "Europe/Amsterdam",
        },
        version=str(datetime.now().strftime("%Y-%m-%d %H:%M")),
    )

    full_schedule = base_schedule.copy()

    # add addional rooms from this local config now, so they are in the correct order
    # for key in rooms:
    #     full_schedule.add_rooms(rooms[key])

    # add events to full_schedule
    for entry in conferences:
        try:
            print(f"\n== Source {entry['name']} \n")
            schedule = entry.schedule(base_schedule)

            if schedule.get('version'):
                full_schedule['version'] += f"; {entry['name']}"
            else:
                log.warning(f'  WARNING: schedule of "{entry}" does not have a version number')

            try:
                print(f"  from {schedule['conference']['start']} to {schedule['conference']['end']}")
                print( "  contains {events_count} events, with local ids from {min_id} to {max_id}".format(**schedule.stats.__dict__))  # noqa
                print( "    local person ids from {person_min_id} to {person_max_id}".format(**schedule.stats.__dict__)) # noqa
                print(f"    rooms: {', '.join(schedule.rooms())}")

            except Exception:
                pass

            if full_schedule.add_events_from(
                schedule,
                id_offset=entry.get("id_offset") or id_offsets.get(entry["name"]) or 0,
                options={
                    "randomize_small_ids": False,
                    "overwrite_slug": True,
                    "remove_title_additions": True,
                    **(entry.options or {}),
                    # "prefix_person_ids": entry.get("prefix"),
                },
                context=entry,
            ):
                print("  success")

        except ScheduleException as e:
            print(e)

        except KeyboardInterrupt:
            exit()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                print("  not yet available (404)")
            else:
                print("  HTTP ERROR: " + str(e))
                if options.exit_when_exception_occours:
                    raise e
        except Exception as e:
            log.error(f"  UNEXPECTED ERROR: {type(e).__name__}: {sys.exc_info()[1]}")
            if options.exit_when_exception_occours:
                raise e

    if options.only_stats:
        exit()

    full_schedule.foreach_event(harmonize_event_type, options)


    # to get proper a state, we first have to remove all event files from the previous run
    if not local or options.git:
        git("rm events/*  >/dev/null")
    os.makedirs('events', exist_ok=True)

    # write seperate file for each event, to get better git diffs
    # TODO: use Event.export()
    def export_event(event: Event):
        origin_system = None
        if isinstance(event, Event):
            origin_system = event.origin.origin_system

        with open("events/{}.json".format(event["guid"]), "w") as fp:
            json.dump(
                {
                    **event,
                    "room_id": full_schedule._room_ids.get(event["room"], None),
                    "origin": origin_system or None,
                },
                fp,
                indent=2,
                cls=ScheduleEncoder,
            )

    full_schedule.foreach_event(export_event)

    # remove overlapping 'Lötworkshop mit Lötchallenge'
    #full_schedule.remove_event(guid='bd75d959-dad1-43b4-81fb-33dfb43c10ec')

    # write all events to one big schedule.json/xml
    write("\nExporting... ")
    # set_validator_filter('strange')
    full_schedule.export("everything")

    # write channel/stages only schedule.json/xml
    streams_schedule = full_schedule.filter("channels", rooms=rooms['channels'])
    replacements = {}
    for stream in rooms['channels']:
        r = streams_schedule.room(guid=stream.guid)
        if r and r['name'] and stream.name and stream.name != r['name']:
            replacements[r['name']] = stream.name
    streams_schedule.rename_rooms(replacements)
    streams_schedule.export("channels")

    # cleaned export for engelsystem etc.
    cleaned_schedule = streams_schedule.copy("channels2")
    cleaned_schedule.remove_room("Jugend Village")
    # merge/remove lightning talks
    cleaned_schedule.remove_event(guid='6553838c-8d09-5d60-8491-94296e3c9caa')
    cleaned_schedule.remove_event(guid='69781345-b8d6-5c42-8444-766f5593e153')
    cleaned_schedule.remove_event(guid='adade555-cb63-5401-93d4-23fe26f4037a')
    cleaned_schedule.remove_event(guid='a866a3ff-6b7c-5dd2-abcc-b83baade8106')
    cleaned_schedule.remove_event(guid='034839e5-ee0c-5909-99c5-646561e5842c')
    lt = cleaned_schedule.event(guid='fc5f078e-bfc5-58c0-9252-e64f81a41fc2')
    lt['duration'] = '0:50'
    cleaned_schedule.export("channels2")

    # expose metadata to own file
    with open("meta.json", "w") as fp:
        json.dump(
            {
                "data": {
                    "version": full_schedule.version(),
                    #"source_urls": list(loaded_schedules.keys()),
                    "rooms": [
                        {
                            **room,
                            "schedule_name": room['name'],
                            "stream": channels.get(room.get('guid', room['name']), Room()).stream
                        }
                        for room in full_schedule.rooms(mode='v2')
                    ],
                    "conferences": conferences,
                },
            },
            fp,
            indent=2,
            cls=ScheduleEncoder,
        )

    print("\nDone")
    print("  version: " + full_schedule.version())

    if options.debug:
        print("\n  rooms: ")
        for room in full_schedule.rooms():
            print("   - " + room)
        print()

        print("\n  channels: ")
        for room in streams_schedule.rooms():
            print("   - " + room)
        print()

    if not local or options.git:
        commit_changes_if_something_relevant_changed(full_schedule)
        # Attention: This method exits the script, if nothing relevant changed
        # TOOD: make this fact more obvious or refactor code


    if not local and "c3data" in targets:
        print("\n== Updating c3data via API…")

        c3data = C3data(full_schedule)
        c3data.process_changed_events(Repo('.'), options)


if __name__ == "__main__":
    main()
