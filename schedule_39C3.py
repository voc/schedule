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
    gen_uuid
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

xc3 = "39c3"
year = 2025


def create_block_schedule(fahrplan):
    block_schedule = Schedule.from_template(f"{xc3} Saal Blöcke", xc3, year, 12, 26, days_count=5)
    rooms = [
        Room(name='Saal 1', guid='ba692ba3-421b-5371-8309-60acc34a3c08', char='O'),
        Room(name='Saal G', guid='7202df07-050c-552f-8318-992f94e40ef3', char='G'),
        Room(name='Saal Z', guid='62251a07-13e4-5a72-bb3c-8528416ee0f5', char='Z'),
        Room(name='Saal F', guid='e58b284a-d3e6-42cc-be2b-7e02c791bf98', char='F'),
        Room(name='Saal X 07',  guid='9001b61b-b1f1-5bcd-89fd-135ed5e43e20', char='X'),
        Room(name='Stage H',    guid='9001b61b-b1f1-5bcd-89fd-135ed5e43e42', char='H'),
        Room(name='Club',       guid='9001b61b-b1f1-5bcd-89fd-135ed5e43e21', char='C'),
        Room(name='Raum 315',   description='C3VOC Hel(l|p)desk', guid='a5b0b1c5-2872-48ee-a7ef-80252af0f76b', char='VHD'),        
        Room(name='Raum 314',   description='C3VOC Office',       guid='a5b0b1c5-2872-48ee-a7ef-80252af0f76c', char='VO'),        
        Room(name='Everywhere', guid='7abcfbfd-4b2f-4fc4-8e6c-6ff854d4936f', char='∀'),
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
            {"start": "14:30:00", "end": "17:00:00", "title": "Afternon"}
        ],
    }

    i = -1
    for day in config:
        i += 1
        j = 0
        for b in config[day]:
            j += 1
            for r in rooms:
                start = dateutil.parser.parse(f"{day}T{b['start']}+01:00")
                end = dateutil.parser.parse(f"{day}T{b['end']}+01:00")
                # fix end, if after midnight
                if (end - start).total_seconds() <= 0:
                    end += dateutil.relativedelta.relativedelta(days=1)

                block_schedule.add_event(Event(
                    title=f"{i if i else ''} {b['title']} {r.char}".strip(),
                    start=start, 
                    end=end, 
                    guid= gen_uuid(f"{xc3}-{i}{j}{r.char}"),
                    room=r,
                    data={
                        "type": "block",
                    }
                ))

    block_schedule.export("block")

def create_himmel_evac_schedule(fahrplan):
    himmel_schedule = fahrplan.copy("Himmel Evac")
    himmel_schedule.rename_rooms({
        'Saal One':    Room(name='Saal One Evac', guid='ba692ba3-421b-5371-8309-60acc34a3c06'),
        'Saal Ground': Room(name='Saal Ground Evac', guid='7202df07-050c-552f-8318-992f94e40ef1'),
        'Saal Zero':   Room(name='Saal Zero Evac', guid='62251a07-13e4-5a72-bb3c-8528416ee0f3'),
    })
    himmel_schedule.export("himmel")

def create_himmel_door_scheudle(fahrplan):
    himmel2_schedule = fahrplan.copy("Himmel Door")
    himmel2_schedule.rename_rooms({
        'Saal One':    Room(name='Saal One Door', guid='ba692ba3-421b-5371-8309-60acc34a3c07'),
        'Saal Ground': Room(name='Saal Ground Door', guid='7202df07-050c-552f-8318-992f94e40ef2'),
        'Saal Zero':   Room(name='Saal Zero Door', guid='62251a07-13e4-5a72-bb3c-8528416ee0f4'),
        'Saal Fuse':   Room(name='Saal Fuse Door', guid='e58b284a-d3e6-42cc-be2b-7e02c791bf97'),
    })
    himmel2_schedule.export("himmel2")


def create_sendezentrum_schedule():
    himmel3_schedule = sendezentrum \
        .schedule(base_schedule) \
        .filter('Himmel3', rooms=[
            Room(name='Saal X 07', guid='f3483ff0-d680-5aed-8f8b-8fc9e191893f')
        ])

    # give Saal X 07 a new guid due to a bug in the engelsystem, as requested by jwacalex
    himmel3_schedule.rename_rooms({
        'Saal X 07': Room(name='Saal X 07', guid='f3483ff0-d680-5aed-8f8b-8fc9e1918940')
    })

    optouts = himmel3_schedule.foreach_event(lambda e: e['guid'] if e['do_not_record'] else None)

    print(f" Removing {len(optouts)} recording optout events from engelsystem sendezentrum schedule")

    for guid in optouts:
        himmel3_schedule.remove_event(guid=guid)

    himmel3_schedule.export("himmel3")
    return True






main_cfp = PretalxConference(
    url=f"https://cfp.cccv.de/{xc3}",
    data={
        "name": "fahrplan",
    },
    use_token=True,
)
hub = GenericConference(
    url=f"https://api.events.ccc.de/congress/{year}/schedule.json",
    data={
        "name": "hub",
    },
)

base_schedule = Schedule(
    conference={
        "url": f"https://events.ccc.de/congress/{year}/",
        "acronym": xc3,
        "title": "9th Chaos Communication Congres",
        "start": f"{year}-12-27T09:30:00+00:00",
        "end": f"{year}-12-30T17:30:00+00:00",
        "daysCount": 4,
        "timeslot_duration": "00:10",
        "time_zone_name": "Europe/Berlin",
    },
    version=str(datetime.now().strftime("%Y-%m-%d %H:%M")),
)

sendezentrum = PretalxConference(
    url=f"https://pretalx.c3voc.de/{xc3}-sendezentrum",
    data={
        "name": "sendezentrum",
    },
)
music = PretalxConference(
    url=f"https://cfp.cccv.de/{xc3}-chaos-computer-music-club",
    data={
        "name": "music",
    },
    use_token=True,
)
punk = PretalxConference(
    url=f"https://cfp.cccv.de/{xc3}-call-for-punk",
    data={
        "name": "punk",
    },
    use_token=True,
)


subconferences: List[GenericConference] = [
    music,
    punk,
    # PretalxConference(
    #    url=f"https://cfp.cccv.de/{xc3}-lightningtalks/",
    #    data={
    #        "name": "lightningtalks",
    #    },
    # ),
    sendezentrum,
    PretalxConference(
        url=f"https://pretalx.c3voc.de/{xc3}-haecksen-workshops-2024",
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
    try:
        print(
            "    local person ids from {person_min_id} to {person_max_id}".format(
                **schedule.stats.__dict__
            )
        )  # noqa
    except Exception:
        pass

    print(f"    rooms: {', '.join(schedule.rooms())}")


def main():
    fahrplan = main_cfp.schedule()
    create_block_schedule(fahrplan)
    create_himmel_evac_schedule(fahrplan)
    create_himmel_door_scheudle(fahrplan)
    create_sendezentrum_schedule()

    everything = hub.schedule()

    loaded_schedules = {}

    print(f"\n== Main programme (= fahrplan) \n")
    schedule_stats(fahrplan)

    merge_schedules = False
    if False:
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

                if merge_schedules:
                    if full_schedule.add_events_from(
                        schedule,
                        id_offset=entry.get("id_offset") or id_offsets.get(entry["name"]) or 0,
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
                log.error(f"  UNEXPECTED ERROR: {type(e).__name__}: {sys.exc_info()[1]}")
                if options.exit_when_exception_occours:
                    raise e

            if options.only_stats:
                exit()

            #full_schedule.foreach_event(harmonize_event_type, options)

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
        commit_changes_if_something_relevant_changed(everything)
        # Attention: This method exits the script, if nothing relevant changed
        # TOOD: make this fact more obvious or refactor code

    if not local and "c3data" in targets:
        print("\n== Updating c3data via API…")

        c3data = C3data(everything)
        c3data.process_changed_events(Repo("."), options)


if __name__ == "__main__":
    main()
