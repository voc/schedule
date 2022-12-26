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

xc3 = "jev22"

# source pad https://lab.nrw/hedgedoc/_hV5kXt9TKuiV0DVsdIwgg
conferences: List[GenericConference] = [
    PretalxConference(
        url="https://pretalx.c3voc.de/fire-shonks-2022",
        data={
            "name": "FireShonks",  # (27.–30.)
            "location": "Remote & Wülfrath",
            "links": [
                "https://events.ccc.de/2022/10/27/fireshonks-cfp/",
                "https://events.haecksen.org/fireshonks/",
            ],
        },
        options={"track": lambda e: e["track"].split(" ")[0]},
    ),
    PretalxConference(
        url="https://cfp.ccc-p.org/rtc22",
        data={
            "name": "Reconnect To Chaos!",  # (27.–30.)
            "location": "Potsdam, Chaostreff",
            "links": ["https://www.ccc-p.org/rtc22/"],
        },
        options={"track": "Potsdam"},
    ),
    PretalxConference(
        url="https://pretalx.c3voc.de/hacking-in-hell-2022",
        data={
            "name": "Hellarious: Hacking in Hell",
            "location": "Brandenburg, Alte Hölle",
            "links": ["https://alte-hoelle.de/"],
        },
        options={"track": "Hellarious"},
    ),
    PretalxConference(
        url="https://pretalx.c3voc.de/xrelog-2022",
        data={
            "name": "xrelog22: Independent Multiverses",  # (28.–30.)
            "location": "Hamburg, FTZ/HAW",
            "links": [
                "https://events.ccc.de/2022/11/13/xrelog22-cfp/",
                "https://matrix.to/#/#xrevent:matrix.org",
            ],
        },
    ),
    WebcalConference(
        url="webcals://ramac.mudbyte.de/remote.php/dav/public-calendars/YTtwyZcXsmZDfSoo/?export",
        data={
            "name": "ChilyConChaos",  # (28.–30.)
            "location": "Gießen/Wetzlar",
            "links": ["https://chilyconchaos.de/"],
        },
        options={
            "track": "Gießen/Wetzlar",
        },
    ),
    PretalxConference(
        url="https://talks.w.icmp.camp/wicmp1",
        data={
            "slug": "wicmp1",
            "name": "Wintergalaktische Club Mate Party",  # (27.–30.)
            "location": "Erlangen, Bits'n'Bugs + ZAM",
            "links": ["https://w.icmp.camp"],
        },
        options={"track": "Erlangen"},
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
        },
    ),
    PretalxConference(
        url="https://pretalx.c3voc.de/hip-berlin-2022",
        data={
            "name": "Hacking in Parallel",  # (27.–30.)
            "location": "Berlin, ETI Schauspielschule + c-base",
            "links": ["https://wiki.hip-berlin.de/"],
        },
        options={
            "track": lambda e: "E.T.I." if e["room"] != "c-base mainhall" else "c-base"
        },
    ),
    PretalxConference(
        url="https://forum.freiraeumen.jetzt/freiraumforum",
        data={
            "name": "Forum für Freiräume - Gib Uns Mehr!",  # (26.–31.)
            "location": "München",
            "links": ["https://events.ccc.de/2022/11/18/ff22-cfp/"],
        },
        options={"track": "Freiräume"},
    ),
    PretalxConference(
        url="https://pretalx.hackwerk.fun/jev-2022",
        data={
            "name": "End-of-Year event",
            "location": "Aalen, Hackwerk",
            "description": "Auch wir würden gerne bei der dezentralen Jahresendveranstaltung mitmachen. Hierzu laden wir vom 29.12-31.12. zum netten Zusammensein mit vielen Chaos-Wesen nach Aalen ein. \n\n Wir schauen bei einigen Glühtschunks und Mate zusammen die Streams auf media.ccc.de an, haben aber auch vor selbst Vorträge zu halten und zu Streamen. \n\n Bitte hier ein Ticket klicken (wir verwenden das Ticketsystem, um die Teilnehmerzahl zu wissen)  – für Talk-Einreichungen haben wir ein Pretalx eingerichtet.",
            "links": [
                "https://tickets.hackwerk.fun/hackwerk/jev2022/",
                "https://pretalx.hackwerk.fun/jev-2022/cfp",
            ],
        },
    ),
    GenericConference(
        url="TBD",
        data={
            "name": "localverse2022",  # (27.–30.)
            "location": "Leipzig",
            "links": [
                "https://dezentrale.space/posts/2022/11/localverse2022-call-for-participation/",
                "https://matrix.to/#/#localverse2022:chat.dezentrale.space",
            ],
        },
    ),
    GenericConference(
        url="https://data.jtbx.de/jev22_ccl/schedule.json",
        data={
            "name": "jev22_ccl",  # (27.–29.)
            "location": "Hamburg",
            "links": [
                "https://curious.bio/2022/11/remote-chaos-experience/",
            ],
        },
        options={"track": "Curious Community Labs"},
    )
]

targets = [
    "filesystem",
    "c3data",
    # "voctoimport",
    # "rc3hub"
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
        Room(guid='c62a781e-48a3-4546-bb5c-dee2080738f7', stream='fireshonks', name="Fireshonks-Stream"),  # Remote
        Room(guid='6f12618c-0f1c-4318-a201-099152f86ac0', stream='s4', name="RTC-Bühne (Sparti)"),  # Potsdam
        Room(guid='0ce1f1b3-35c6-48ee-b3db-1c54e85f36b4', stream='s6', name="Bierschoine"),  # Alte Hölle
        Room(guid='99808216-837b-11ed-85fb-6c400891b752', stream='s2', name='Seminarraum'),  # WICMP, Erlangen
        Room(guid='568cabc6-82f2-11ed-82f7-cf29158272bb', stream='s1', name="Vortragsraum 1 - Ahlam - H2-1.6"),  # Freiräume
        Room(guid='64f358c2-82f2-11ed-b6f2-370ab4c5fdf0', stream='s5', name="Vortragsraum 2 - Bhavani - H1-5.2"),  # Freiräume
        Room(guid='ad28953f-122e-4293-836d-860320183a1c', stream='xrelog22'),  # xrelog22
        # TODO: Where is the Curious Community Labs scheulde with more structure? https://curious.bio/2022/11/remote-chaos-experience/
        # Room(stream='', name='Curious Community Labs')
    ],
    "rooms": [],
    "music": [],
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
            "acronym": "jev22",
            "title": "Dezentrale Jahresendveranstaltungen",
            "start": "2022-12-26",
            "end": "2022-12-31",
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
                    "remove_title_additions": True,
                    **(entry.options or {}),
                    "prefix_person_ids": entry.get("prefix"),
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

    # remove overlapping 'Lötworkshop mit Lötchallenge' 
    full_schedule.remove_event(guid='bd75d959-dad1-43b4-81fb-33dfb43c10ec')

    # set_validator_filter(["precomputed", "fire-shonks-2022", "hip-berlin-2022"])
    # write all events to one big schedule.json/xml
    write("\nExporting... ")
    # set_validator_filter('strange')
    full_schedule.export("everything")
    full_schedule.export_filtered("channels", rooms=rooms['channels'])

    # expose metadata to own file
    with open("meta.json", "w") as fp:
        json.dump(
            {
                "data": {
                    "version": full_schedule.version(),
                    # 'source_urls': list(loaded_schedules.keys()),
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

    print("\n  rooms: ")
    for room in full_schedule.rooms():
        print("   - " + room)
    print()

    if not local or options.git:
        commit_changes_if_something_relevant_changed(full_schedule)

    if "c3data" in targets:
        print("\n== Updating c3data via API…")

        c3data = C3data(full_schedule)
        c3data.process_changed_events(Repo('.'), options)


if __name__ == "__main__":
    main()
