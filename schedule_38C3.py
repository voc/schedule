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

xc3 = "38c3"

main_cfp = GenericConference(
    url="https://fahrplan.events.ccc.de/congress/2024/fahrplan/schedule/export/schedule.json",
    data={
    },
)
hub = GenericConference(
    url="https://api.events.ccc.de/congress/2024/schedule.json",
    data={
        "name": "hub",
    },
)

base_schedule = Schedule(
    conference={
        "url": "https://events.ccc.de/congress/2024/",
        "acronym": "38c3",
        "title": "38th Chaos Communication Congress",
        "start": "2024-12-27T09:30:00+00:00",
        "end": "2024-12-30T21:00:00+00:00",
        "daysCount": 4,
        "timeslot_duration": "00:10",
        "time_zone_name": "Europe/Berlin",
    },
    version=str(datetime.now().strftime("%Y-%m-%d %H:%M")),
)

subconferences: List[GenericConference] = [
    PretalxConference(
        url="https://cfp.cccv.de/38c3-community-stages",
        data={
            "name": "community-stages",
        },
    ),
    PretalxConference(
        url="https://cfp.cccv.de/38c3-chaos-computer-music-club",
        data={
            "name": "music",
        },
    ),
    # PretalxConference(
    #    url="https://cfp.cccv.de/38c3-lightningtalks/",
    #    data={
    #        "name": "lightningtalks",
    #    },
    # ),
    PretalxConference(
        url="https://pretalx.c3voc.de/38c3-sendezentrum",
        data={
            "name": "sendezentrum",
        },
    ),
    PretalxConference(
        url="https://pretalx.c3voc.de/38c3-haecksen-workshops-2024",
        data={
            "name": "haecksen",
        },
    ),
    PretalxConference(
        url="https://fahrplan.alpaka.space/jugend-hackt-38c3-2024",
        data={
            "name": "jugend",
        },
    ),
]

targets = [
    "filesystem",
    "c3data",
    # "voctoimport",
    # "rc3hub"
]

id_offsets = {}

# this list/map is required to sort the events in the schedule.xml in the correct way
# other rooms/assemblies are added at the end on demand.
rooms = {}

channels = {}

output_dir = "/srv/www/" + xc3
secondary_output_dir = "./" + xc3
if len(sys.argv) == 2:
    output_dir = sys.argv[1]

local = ensure_folders_exist(output_dir, secondary_output_dir)

def create_himmel_schedule(fahrplan):
    himmel_schedule = fahrplan.copy("himmel")
    himmel_schedule.rename_rooms({
        'Saal 1':      Room(name='Saal 1 Evac', guid='ba692ba3-421b-5371-8309-60acc34a3c06'),
        'Saal GLITCH': Room(name='Saal GLITCH Evac', guid='7202df07-050c-552f-8318-992f94e40ef1'),
        'Saal ZIGZAG': Room(name='Saal ZIGZAG Evac', guid='62251a07-13e4-5a72-bb3c-8528416ee0f3'),
    })
    himmel_schedule.export("himmel")

    himmel2_schedule = fahrplan.copy("himmel")
    himmel2_schedule.rename_rooms({
        'Saal 1':      Room(name='Saal 1 Door', guid='ba692ba3-421b-5371-8309-60acc34a3c07'),
        'Saal GLITCH': Room(name='Saal GLITCH Door', guid='7202df07-050c-552f-8318-992f94e40ef2'),
        'Saal ZIGZAG': Room(name='Saal ZIGZAG Door', guid='62251a07-13e4-5a72-bb3c-8528416ee0f4'),
    })
    himmel2_schedule.export("himmel2")

    return himmel_schedule


def schedule_stats(schedule):
    print(f"  system {schedule['base_url']}")
    print(
        f"  from {schedule['conference']['start']} to {schedule['conference']['end']}"
    )
    print(
        "  contains {events_count} events, with local ids from {min_id} to {max_id}".format(
            **schedule.stats.__dict__
        )
    )  # noqa
    print(
        "    local person ids from {person_min_id} to {person_max_id}".format(
            **schedule.stats.__dict__
        )
    )  # noqa
    print(f"    rooms: {', '.join(schedule.rooms())}")


def main():
    fahrplan = main_cfp.schedule()
    create_himmel_schedule(fahrplan)

    everything = hub.schedule()
    loaded_schedules = {}

    print(f"\n== Main programme (= fahrplan) \n")
    schedule_stats(fahrplan)

    merge_schedules = False
    if True:
        # get events from subconferences
        for entry in subconferences:
            try:
                print(f"\n== Source {entry['name']} \n")
                schedule = entry.schedule(base_schedule)
                loaded_schedules[entry["name"]] = schedule

                if schedule.get("version"):
                    if merge_schedules:
                        full_schedule["version"] += f"; {entry['name']}"
                else:
                    log.warning(
                        f'  WARNING: schedule of "{entry}" does not have a version number'
                    )

                try:
                    schedule_stats(schedule)
                except Exception:
                    pass

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


    # to get proper a state, we first have to remove all event files from the previous run
    if not local or options.git:
        git("rm events/*  >/dev/null")
    os.makedirs("events", exist_ok=True)

    fahrplan.foreach_event(lambda e: e.export("events/", "-origin"))
    everything.foreach_event(lambda e: e.export("events/", "-hub"))
    #for schedule in loaded_schedules:
    #   schedule.foreach_event(lambda e: e.export("events/", "-origin"))

    # remove overlapping 'Lötworkshop mit Lötchallenge'
    # full_schedule.remove_event(guid='bd75d959-dad1-43b4-81fb-33dfb43c10ec')

    # write all events to one big schedule.json/xml
    write("\nExporting... ")
    # set_validator_filter('strange')
    everything.export("everything")


    # expose metadata to own file
    with open("meta.json", "w") as fp:
        json.dump(
            {
                "data": {
                    "version": fahrplan.version(),
                    "source_urls": list(loaded_schedules.keys()),
                    "rooms": [
                        {
                            **room,
                            "schedule_name": room["name"],
                            "stream": channels.get(
                                room.get("guid", room["name"]), Room()
                            ).stream,
                        }
                        for room in everything.rooms(mode="v2")
                    ],
                    "conferences": subconferences,
                },
            },
            fp,
            indent=2,
            cls=ScheduleEncoder,
        )

    print("\nDone")
    print("  fahrplan version: " + fahrplan.version())
    print("  hub      version: " + everything.version())



    if not local or options.git:
        commit_changes_if_something_relevant_changed(everything)
        # Attention: This method exits the script, if nothing relevant changed
        # TOOD: make this fact more obvious or refactor code

    if not local and "c3data" in targets:
        print("\n== Updating c3data via API…")

        c3data = C3data(everything)
        c3data.process_changed_events(Repo("."), options)


if __name__ == "__main__":
    main()
