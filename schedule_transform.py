#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import os
import json
import pytz
import sys
from datetime import datetime

from voc import Logger
from voc.schedule import Schedule
from voc.git import export_event_files, postprocessing

from voc.pretalx import PretalxConference
from voc.tools import DefaultOptionParser, write, ensure_folders_exist

local = False

log = Logger(__name__)
parser = DefaultOptionParser()
parser.add_argument("acronym")
args = parser.parse_args()

tz = pytz.timezone("Europe/Amsterdam")

conference = PretalxConference(
    url="https://pretalx.c3voc.de/" + args.acronym,
    data={
    },
    options={
    },
)

targets = []

output_dir = "/srv/www/" + args.acronym
secondary_output_dir = "./" + args.acronym
if len(sys.argv) == 2:
    output_dir = sys.argv[1]

local = ensure_folders_exist(output_dir, secondary_output_dir)
local = True

def main():
    #schedule = conference.schedule()
    schedule = Schedule.from_file("schedule.json")
    schedule._generate_stats(verbose=True)

    if args.only_stats:
        exit()

    export_event_files(schedule, args, local)

    # write all events to one big schedule.json/xml
    write("\nExporting... ")
    schedule.export(args.acronym)

    print("\nDone")
    print("  version: " + schedule.version())

    if False:
        postprocessing(schedule, args, local, [
            "filesystem",
            # "c3data",
            # "voctoimport"
        ])


if __name__ == "__main__":
    main()
