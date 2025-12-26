#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import os
from typing import List
import dateutil
import requests
import json
import pytz
import sys
import optparse
from datetime import datetime

from locations.cch import CCH
Rooms = CCH.Rooms

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
    write,
    ensure_folders_exist,
    gen_uuid,
)

tz = pytz.timezone("Europe/Amsterdam")
local = False

parser = optparse.OptionParser()
parser.add_option(
    "--task",
    "-t",
    action="append",
    dest="tasks",
    default=[],
    help="Task(s) to perform, defaults to all",
)
parser.add_option("--online", action="store_true", dest="online", default=False)
parser.add_option(
    "--fail", action="store_true", dest="exit_when_exception_occours", default=local
)
parser.add_option("--stats", action="store_true", dest="only_stats", default=False)
parser.add_option("--git", action="store_true", dest="git", default=False)
parser.add_option("--debug", action="store_true", dest="debug", default=local)

log = Logger(__name__)
options, args = parser.parse_args()

x = 39
xc3 = "39C3"
year = 2025

def create_buildupteardown_schedule():
    buildupteardown_schedule = Schedule.from_template(f"{xc3} C3VOC BuildUp & Teardown", xc3, year, 12, 18, days_count=14)
    rooms = [
        Rooms.S1, Rooms.SG, Rooms.SZ, Rooms.SF,
        Rooms.SX07,
        Rooms.R313, Rooms.R314, Rooms.R315
    ]
    buildupteardown_schedule.add_rooms(rooms)

    config = {
        "2025-12-19": [
            {"start": "09:00:00", "end": "13:00:00", "title": "Morning"},
            {"start": "13:30:00", "end": "19:00:00", "title": "Afternoon"},
            {"start": "20:00:00", "end": "00:00:00", "title": "Evening"},
            {"start": "00:00:00", "end": "03:00:00", "title": "Night"}
        ],
        "2025-12-20": [
            {"start": "09:00:00", "end": "13:00:00", "title": "Morning"},
            {"start": "13:30:00", "end": "19:00:00", "title": "Afternoon"},
            {"start": "20:00:00", "end": "00:00:00", "title": "Evening"},
            {"start": "00:00:00", "end": "03:00:00", "title": "Night"}
        ],
        "2025-12-21": [
            {"start": "09:00:00", "end": "13:00:00", "title": "Morning"},
            {"start": "13:30:00", "end": "19:00:00", "title": "Afternoon"},
            {"start": "20:00:00", "end": "00:00:00", "title": "Evening"},
            {"start": "00:00:00", "end": "03:00:00", "title": "Night"}
        ],
        "2025-12-22": [
            {"start": "09:00:00", "end": "13:00:00", "title": "Morning"},
            {"start": "13:30:00", "end": "19:00:00", "title": "Afternoon"},
            {"start": "20:00:00", "end": "00:00:00", "title": "Evening"},
            {"start": "00:00:00", "end": "03:00:00", "title": "Night"}
        ],
        "2025-12-23": [
            {"start": "09:00:00", "end": "13:00:00", "title": "Morning"},
            {"start": "13:30:00", "end": "19:00:00", "title": "Afternoon"},
            {"start": "20:00:00", "end": "00:00:00", "title": "Evening"},
            {"start": "00:00:00", "end": "03:00:00", "title": "Night"}
        ],
        "2025-12-24": [
            {"start": "09:00:00", "end": "13:00:00", "title": "Morning"},
            {"start": "13:30:00", "end": "19:00:00", "title": "Afternoon"},
            {"start": "20:00:00", "end": "00:00:00", "title": "Evening"},
            {"start": "00:00:00", "end": "03:00:00", "title": "Night"}
        ],
        "2025-12-25": [
            {"start": "09:00:00", "end": "13:00:00", "title": "Morning"},
            {"start": "13:30:00", "end": "19:00:00", "title": "Afternoon"},
            {"start": "20:00:00", "end": "00:00:00", "title": "Evening"},
            {"start": "00:00:00", "end": "03:00:00", "title": "Night"}
        ],
        "2025-12-26": [
            {"start": "09:00:00", "end": "13:00:00", "title": "Morning"},
            {"start": "13:30:00", "end": "19:00:00", "title": "Afternoon"},
            {"start": "20:00:00", "end": "00:00:00", "title": "Evening"},
            {"start": "00:00:00", "end": "03:00:00", "title": "Night"}
        ],
        "2025-12-30": [
            {"start": "17:30:00", "end": "19:00:00", "title": "Afternoon"},
            {"start": "19:30:00", "end": "00:00:00", "title": "Evening"},
            {"start": "00:00:00", "end": "03:00:00", "title": "Night"}
        ],
        "2025-12-31": [
            {"start": "09:00:00", "end": "13:00:00", "title": "Morning"},
            {"start": "13:30:00", "end": "19:00:00", "title": "Afternoon"},
        ],
    }

    i = -1
    # for each day
    for day in config:
        i += 1
        j = 0
        # for each block
        for b in config[day]:
            j += 1
            # for each room
            for r in rooms:
                start = dateutil.parser.parse(f"{day}T{b['start']}+01:00")
                end = dateutil.parser.parse(f"{day}T{b['end']}+01:00")
                # fix end, if after midnight
                if (end - start).total_seconds() <= 0:
                    end += dateutil.relativedelta.relativedelta(days=1)

                buildupteardown_schedule.add_event(Event(
                    title=f"{i if i else ''} {b['title']} {r.char}".strip(),
                    start=start,
                    end=end,
                    guid=gen_uuid(f"{xc3}-btd_{i}{j}{r.char}"),
                    room=r,
                    type="buildupteardown",
                    # TODO why do we need an empty dict here? Otherwise no new instances are created
                    data={}
                ))

    buildupteardown_schedule.export("buildupteardown")

def create_block_schedule():
    block_schedule = Schedule.from_template(
        f"{xc3} Saal Blöcke", xc3, year, 12, 26, days_count=5
    )
    block_schedule = Schedule.from_template(f"{xc3} Saal Blockschichten", xc3, year, 12, 26, days_count=5)
    rooms = [
        Rooms.S1, Rooms.SG, Rooms.SZ, Rooms.SF, 
        Rooms.SX07, Rooms.STH, Rooms.CLUB,
        Rooms.S10, 
        Rooms.R313, Rooms.R314, Rooms.R315,
        Rooms.E
    ]

    block_schedule.add_rooms(rooms)
    
    config = {
        "2025-12-26": [
            {"start": "14:30:00", "end": "19:00:00", "title": "Aufbau"}
        ],

        "2025-12-27": [
            {"start": "10:00:00", "end": "14:30:00", "title": "Morning"},
            {"start": "14:30:00", "end": "18:15:00", "title": "Afternoon"},
            #{"start": "18:15:00", "end": "19:00:00", "title": "Break"},
            {"start": "19:00:00", "end": "23:00:00", "title": "Evening"},
            {"start": "23:00:00", "end": "02:00:00", "title": "Night"}
        ],

        "2025-12-28": [
            {"start": "09:30:00", "end": "14:30:00", "title": "Morning"},
            {"start": "14:30:00", "end": "18:15:00", "title": "Afternoon"},
            #{"start": "18:15:00", "end": "19:00:00", "title": "Break"},
            {"start": "19:00:00", "end": "23:00:00", "title": "Evening"},
            {"start": "23:00:00", "end": "03:00:00", "title": "Night"}
        ],

        "2025-12-29": [
            {"start": "09:00:00", "end": "14:30:00", "title": "Morning"},
            {"start": "14:30:00", "end": "18:30:00", "title": "Afternoon"},
            #{"start": "18:15:00", "end": "19:00:00", "title": "Break"},
            {"start": "19:00:00", "end": "23:00:00", "title": "Evening"},
            {"start": "23:00:00", "end": "03:00:00", "title": "Night"}
        ],

        "2025-12-30": [
            {"start": "10:00:00", "end": "14:30:00", "title": "Morning"},
            {"start": "14:30:00", "end": "17:00:00", "title": "Afternoon"}
        ],
    }

    i = -1
    # for each day
    for day in config:
        i += 1
        j = 0
        # for each block
        for b in config[day]:
            j += 1
            # for each room
            for r in rooms:
                start = dateutil.parser.parse(f"{day}T{b['start']}+01:00")
                end = dateutil.parser.parse(f"{day}T{b['end']}+01:00")
                # fix end, if after midnight
                if (end - start).total_seconds() <= 0:
                    end += dateutil.relativedelta.relativedelta(days=1)

                block_schedule.add_event(
                    Event(
                        title=f"{i if i else ''} {b['title']} {r.char}".strip(),
                        start=start,
                        end=end,
                        guid=gen_uuid(f"{xc3}-{i}{j}{r.char}"),
                        room=r,
                        type="block",
                        # TODO why do we need an empty dict here? Otherwise no new instances are created
                        data=dict()
                    )
                )

    #block_schedule.print_stats()
    block_schedule.export("block")


def create_himmel_evac_schedule(fahrplan):
    himmel_schedule = fahrplan.copy("Himmel Evac")
    himmel_schedule.rename_rooms({
        "One":    Rooms.S1,
        "Ground": Rooms.SG,
        "Zero":   Rooms.SZ,
        "Fuse":   Rooms.SF,
    })
    #himmel_schedule.remove_room("Fuse")
    himmel_schedule.print_stats()
    himmel_schedule.export("himmel")


def create_himmel_door_schedule(fahrplan):
    himmel2_schedule = fahrplan.copy("Himmel Door")
    himmel2_schedule.rename_rooms(
        {
            "One":    Rooms.S1,
            "Ground": Rooms.SG,
            "Zero":   Rooms.SZ,
            "Fuse":   Rooms.SF,
        }
    )
    himmel2_schedule.print_stats()
    himmel2_schedule.export("himmel2")


def create_sendezentrum_schedule(sendezentrum, base_schedule):
    himmel3_schedule = sendezentrum.schedule(base_schedule).filter(
        "Himmel3",
        rooms=[
            Room(name="Saal X 07", guid="f3483ff0-d680-5aed-8f8b-8fc9e191893f")
        ],
    )

    # give Saal X 07 a new guid due to a bug in the engelsystem, as requested by jwacalex
    himmel3_schedule.rename_rooms(
        {
            "Saal X 07": Room(
                name="Saal X 07", guid="f3483ff0-d680-5aed-8f8b-8fc9e1918940"
            )
        }
    )

    optouts = himmel3_schedule.foreach_event(
        lambda e: e["guid"] if e["do_not_record"] else None
    )

    print(
        f" Removing {len(optouts)} recording optout events from engelsystem sendezentrum schedule"
    )

    for guid in optouts:
        himmel3_schedule.remove_event(guid=guid)

    himmel3_schedule.print_stats()
    himmel3_schedule.export("himmel3")
    return True


class Congress:
    def __init__(self, nr, xc3, year) -> None:
        self.main_cfp = PretalxConference(
            url=f"https://cfp.cccv.de/{xc3}",
            data={
                "name": "fahrplan",
            },
            use_token=True,
        )
        self.hub = GenericConference(
            url=f"https://api.events.ccc.de/congress/{year}/schedule.json",
            data={
                "name": "hub",
            },
        )

        self.base_schedule = Schedule(
            conference={
                "url": f"https://events.ccc.de/congress/{year}/",
                "acronym": xc3,
                "title": f"{x}th Chaos Communication Congres",
                "start": f"{year}-12-27T09:30:00+00:00",
                "end": f"{year}-12-30T17:30:00+00:00",
                "daysCount": 4,
                "timeslot_duration": "00:10",
                "time_zone_name": "Europe/Berlin",
            },
            version=str(datetime.now().strftime("%Y-%m-%d %H:%M")),
        )

        self.sendezentrum = PretalxConference(
            url=f"https://pretalx.c3voc.de/{xc3}-sendezentrum",
            data={
                "name": "sendezentrum",
            },
        )
        self.music = PretalxConference(
            url=f"https://cfp.cccv.de/{xc3}-chaos-computer-music-club",
            data={
                "name": "music",
            },
            use_token=True,
        )
        self.punk = PretalxConference(
            url=f"https://cfp.cccv.de/{xc3}-call-for-punk",
            data={
                "name": "punk",
            },
            use_token=True,
        )

        self.subconferences: List[GenericConference] = [
            self.music,
            self.punk,
            # PretalxConference(
            #    url=f"https://cfp.cccv.de/{xc3}-lightningtalks/",
            #    data={
            #        "name": "lightningtalks",
            #    },
            # ),
            self.sendezentrum,
            PretalxConference(
                url=f"https://pretalx.c3voc.de/{xc3}-haecksen-workshops-{year}",
                data={
                    "name": "haecksen",
                },
            ),
            PretalxConference(
                url=f"https://pretalx.wikimedia.de/{xc3}-{year}",
                data={
                    "name": "free-knowledge",
                },
            ),
            PretalxConference(
                url=f"https://pretalx.chaos.jetzt/jugend",
                data={
                    "name": "jugend",
                },
            ),
        ]

        self.loaded_schedules = {}

        self.targets = [
            "filesystem",
            "c3data",
            # "voctoimport",
            # "rc3hub"
        ]

        # this list/map is required to sort the events in the schedule.xml in the correct way
        # other rooms/assemblies are added at the end on demand.
        self.rooms = {}
        self.channels = {}

        global output_dir, secondary_output_dir, local
        output_dir = "/srv/www/" + xc3
        secondary_output_dir = "./" + xc3
        if len(sys.argv) == 2:
            output_dir = sys.argv[1]

        local = ensure_folders_exist(output_dir, secondary_output_dir)

    def merge_schedules(self, merge=True):
        # get events from subconferences
        for entry in self.subconferences:
            try:
                print(f"\n== Source {entry['name']} \n")
                schedule = entry.schedule(self.base_schedule)
                self.loaded_schedules[entry["name"]] = schedule

                if schedule.get("version"):
                    if merge:
                        full_schedule["version"] += f"; {entry['name']}"
                else:
                    log.warning(
                        f'  WARNING: schedule of "{entry}" does not have a version number'
                    )

                try:
                    schedule_stats(schedule)
                except Exception:
                    pass

                if full_schedule.add_events_from(
                    schedule,
                    id_offset=entry.get("id_offset")
                    or id_offsets.get(entry["name"])
                    or 0,
                    options={
                        # "randomize_small_ids": False,
                        # "overwrite_slug": True,
                        # "remove_title_additions": True,
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
                log.error(
                    f"  UNEXPECTED ERROR: {type(e).__name__}: {sys.exc_info()[1]}"
                )
                if options.exit_when_exception_occours:
                    raise e

            if options.only_stats:
                exit()

            # full_schedule.foreach_event(harmonize_event_type, options)


def main():
    conference = Congress(x, xc3, year)
    fahrplan = conference.main_cfp.schedule()

    # if you want to create block and buildupteardown schedules, 
    # use -t create_block_schedule and/or -t create_buildupteardown_schedule CLI options
    # create_block_schedule()
    # create_buildupteardown_schedule()
    create_himmel_evac_schedule(fahrplan)
    create_himmel_door_schedule(fahrplan)
    create_sendezentrum_schedule(conference.sendezentrum, conference.base_schedule)


    return

    everything = conference.hub.schedule()

    print(f"\n== Main programme (= fahrplan) \n")
    conference.schedule_stats(fahrplan)

    # to get proper a state, we first have to remove all event files from the previous run
    if not local or options.git:
        git("rm events/*  >/dev/null")
    os.makedirs("events", exist_ok=True)

    fahrplan.foreach_event(lambda e: e.export("events/", "-origin"))
    everything.foreach_event(lambda e: e.export("events/", "-hub"))

    write("\nExporting... ")

    # set_validator_filter('strange')
    everything.export("everything")

    # expose metadata to own file
    with open("meta.json", "w") as fp:
        json.dump(
            {
                "data": {
                    "version": fahrplan.version(),
                    "source_urls": list(conference.loaded_schedules.keys()),
                    "rooms": [
                        {
                            **room,
                            "schedule_name": room["name"],
                            "stream": conference.channels.get(
                                room.get("guid", room["name"]), Room()
                            ).stream,
                        }
                        for room in everything.rooms(mode="v2")
                    ],
                    "conferences": conference.subconferences,
                },
            },
            fp,
            indent=2,
            cls=ScheduleEncoder,
        )

    print("\nDone")
    print("  fahrplan version: " + fahrplan.version())
    print("  hub      version: " + everything.version())

    if options.debug:
        print("\n  rooms: ")
        for room in full_schedule.rooms():
            print("   - " + room)
        print()

    if not local or options.git:
        commit_changes_if_something_relevant_changed(everything)
        # Attention: This method exits the script, if nothing relevant changed
        # TOOD: make this fact more obvious or refactor code

    if not local and "c3data" in targets:
        print("\n== Updating c3data via API…")

        c3data = C3data(everything)
        c3data.process_changed_events(Repo("."), options)


if __name__ == "__main__":
    if len(options.tasks) == 0:
        main()
    for task in options.tasks:
        if task in globals() and callable(globals()[task]):
            globals()[task]()
        else:
            log.error(f" Unknown task '{task}'")
            exit(-2)
