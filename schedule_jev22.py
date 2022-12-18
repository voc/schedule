#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

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
    Logger
)
from voc.schedule import set_validator_filter
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

xc3 = "jev22"

# source pad https://lab.nrw/hedgedoc/_hV5kXt9TKuiV0DVsdIwgg
conferences = [
    PretalxConference(
        url="https://pretalx.c3voc.de/hip-berlin-2022",
        data={
            "name": "Hacking in Parallel",  # (27.–30.)
            "location": "Berlin, c-base",
            "links": ["https://wiki.hip-berlin.de/"],
        },
        options={
            "track": "c-base"
        }
    ),
    PretalxConference(
        "TBD",
        {
            "name": "dezentrale Chaos-Culture",  # (27.–28.)
            "location": "Bielefeld, Digitalcourage",
            "links": ["https://digitalcourage.de/"],
        },
    ),
    PretalxConference(
        "https://pretalx.c3voc.de/hacking-in-hell-2022",
        {
            "name": "Hellarious: Hacking in Hell",
            "location": "Brandenburg, Alte Hölle",
            "links": ["https://alte-hoelle.de/"],
        },
        options={
            "track": "Hell"
        }
    ),
    PretalxConference(
        "https://pretalx.c3voc.de/xrelog-2022",
        {
            "name": "xrelog22: Independent Multiverses",  # (28.–30.)
            "location": "Hamburg, FTZ/HAW",
            "links": [
                "https://events.ccc.de/2022/11/13/xrelog22-cfp/",
                "https://matrix.to/#/#xrevent:matrix.org",
            ],
        },
    ),
    GenericConference(
        "TBD",
        {
            "name": "localverse2022",  # (27.–30.)
            "location": "Leipzig",
            "links": [
                "https://dezentrale.space/posts/2022/11/localverse2022-call-for-participation-20221118/",
                "https://matrix.to/#/#localverse2022:chat.dezentrale.space",
            ],
        },
    ),
    PretalxConference(
        "https://forum.freiraeumen.jetzt/freiraumforum",
        {
            "name": "Forum für Freiräume - Gib Uns Mehr!",  # (26.–31.)
            "location": "München",
            "links": ["https://events.ccc.de/2022/11/18/ff22-cfp/"],
        },
    ),
    PretalxConference(
        "https://cfp.ccc-p.org/rtc22",
        {
            "name": "Reconnect To Chaos!",  # (27.–30.)
            "location": "Potsdam, Chaostreff",
            "links": ["https://www.ccc-p.org/rtc22/"],
        },
    ),
    PretalxConference(
        "https://pretalx.c3voc.de/fire-shonks-2022",
        {
            "name": "FireShonks",  # (27.–30.)
            "location": "Remote & Wülfrath",
            "links": [
                "https://events.ccc.de/2022/10/27/fireshonks-cfp/",
                "https://events.haecksen.org/fireshonks/",
            ],
        },
    ),
    PretalxConference(
        "https://talks.w.icmp.camp",
        {
            "slug": "wicmp1",
            "name": "Wintergalaktische Club Mate Party",  # (27.–30.)
            "location": "Erlangen, Bits'n'Bugs + ZAM",
            "links": ["https://w.icmp.camp"],
        },
    ),
]

targets = [
    "filesystem",
    # 'voctoimport',
    # 'rc3hub'
]

id_offsets = {
    #   when 10 additional speakers are created there
    # c3voc preatax schedule local ids's range from 120 to till >500
}


# this list/map is required to sort the events in the schedule.xml in the correct way
# other rooms/assemblies are added at the end on demand.
rooms = {
    "channels": [
        # channels with video recordings/livestream – same order as streaming website
    ],
    "rooms": [],
    "music": [],
}

output_dir = "/srv/www/" + xc3
secondary_output_dir = "./" + xc3
if len(sys.argv) == 2:
    output_dir = sys.argv[1]

local = ensure_folders_exist(output_dir, secondary_output_dir)


def main():
    base_schedule = Schedule(conference={
        "acronym": "jev22",
        "title": "Dezentrale Jahresendveranstaltungen",
        "start": "2022-12-27",
        "end": "2022-12-30",
        "daysCount": 4,
        "timeslot_duration": "00:15",
        "time_zone_name": "Europe/Amsterdam"
    }, version=str(datetime.now()))

    full_schedule = base_schedule.copy()

    # add addional rooms from this local config now, so they are in the correct order
    for key in rooms:
        full_schedule.add_rooms(rooms[key])

    # add room guid's to schedule class
    for entry in conferences:
        if entry.get("room_guid"):
            full_schedule._room_ids[entry["stage"] or entry["name"]] = entry[
                "room_guid"
            ]

    # add events from additional_schedule's to full_schedule
    for entry in conferences:
        try:
            print(f"\n== Conference {entry['name']} ({entry['location']})")
            schedule = entry.schedule(base_schedule)

            if schedule.get('version'):
                full_schedule['version'] += f"; {entry['name']}"
            else:
                log.warn(f'  WARNING: schedule of "{entry}" does not have a version number')

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
                    "randomize_small_ids": True,
                    "overwrite_slug": True,
                    **(entry.get("options") or {}),
                    "prefix_person_ids": entry.get("prefix"),
                },
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

    # write all events from the channels to a own schedule.json/xml
    #  export_stages_schedule(full_schedule)
    #  export_streams_schedule(full_schedule)

    # to get proper a state, we first have to remove all event files from the previous run
    if not local or options.git:
        git("rm events/*")

    # write seperate file for each event, to get better git diffs
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

    # set_validator_filter(["precomputed", "fire-shonks-2022", "hip-berlin-2022"])
    # write all events to one big schedule.json/xml
    write("\nExporting... ")
    full_schedule.export("everything")

    # expose metadata to own file
    with open("meta.json", "w") as fp:
        json.dump(
            {
                "data": {
                    "version": full_schedule.version(),
                    # 'source_urls': list(loaded_schedules.keys()),
                    "conferences": conferences,
                    "rooms": [
                        {
                            "guid": full_schedule._room_ids.get(room, None),
                            "schedule_name": room,
                        }
                        for room in full_schedule.rooms()
                    ],
                },
            },
            fp,
            indent=2,
            cls=ScheduleEncoder,
        )

    print("\nDone")
    print("  version: " + full_schedule.version())

    print("\n  rooms: ")
    for room in full_schedule.rooms():
        print("   - " + room)
    print()

    if not local or options.git:
        commit_changes_if_something_relevant_changed(full_schedule)


if __name__ == "__main__":
    main()
