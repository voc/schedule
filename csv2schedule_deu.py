#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import locale
import argparse
import os
import requests
import json
from collections import OrderedDict
from datetime import datetime, timedelta
import csv
import hashlib
import pytz
import math

from voc.tools import normalise_string, gen_uuid, get_id
from voc.schedule import Schedule, Event

days = []
tz = pytz.timezone('Europe/Amsterdam')
locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')


parser = argparse.ArgumentParser()
parser.add_argument('acronym', help='the event acronym')
parser.add_argument('--offline', action='store_true')
parser.add_argument('--verbose', '-v', action='store_true')
parser.add_argument('--url', action='store')
parser.add_argument('--output-folder', '-o', action='store', dest='output_folder')
parser.add_argument('--default-language', '-lang' , action='store', dest='default_language', default='de')
parser.add_argument('--default-talk-length', '-length' , type=int, action='store', dest='default_talk_length', default=30, help='default length of a talk in minutes, will be cut when overlapping with other talk')
parser.add_argument('--split-persons', action='store_true', dest='split_persons')

# output file name (prefix)?
# output dir (base) as config option?

print('')

args = parser.parse_args()
acronym = args.acronym
if args.url:
    source_csv_url = args.url
    offline = args.offline
else:
    source_csv_url = None
    offline = True
    print("No URL given, using CSV file from disk\n")

if args.output_folder:
    output_dir = args.output_folder
else:
    output_dir = "./{}/".format(acronym)
#output_dir = '/srv/www/schedule/' + acronym


# specifies the date format used in the CSV file respectivly the google docs spreadsheet
date_format = '%Y-%m-%d %H:%M'
default_talk_length = timedelta(minutes=args.default_talk_length)

# Coloum keys of CSV
if args.default_language == 'en':
    date = 'Date'
    time = 'Time'
    title = 'Title'
    description = 'Description'
    room = 'Room'
    persons = 'Presenter'
else:
    date = 'Datum'
    time = 'Uhrzeit'
    title = 'Title'
    description = 'Beschreibung'
    room = 'Raum'
    persons = 'Vortragende'
# end config

if not os.path.exists(output_dir):
    os.mkdir(output_dir)
os.chdir(output_dir)


def main():
    process(acronym, 0, source_csv_url)


def process(acronym, base_id, source_csv_url):
    print('Processing ' + acronym)

    if not offline:
        print(" requesting schedule source from url")
        schedule_r = requests.get(source_csv_url)
        # don't ask me why google docs announces by header? that it will send latin1 and then sends utf8...
        schedule_r.encoding = 'utf-8'

        if schedule_r.ok is False:
            raise Exception("  Requesting schedule from CSV source url failed, HTTP code {0} from {1}.".format(schedule_r.status_code, source_csv_url))

        with open('schedule-' + acronym + '.csv', 'w') as f:
            f.write(schedule_r.text)

    print(" parsing CSV file")
    csv_schedule = []
    max_date = None
    min_date = None
    conference_title = None
    version = None

    filename = 'schedule-' + acronym + '.csv'
    if sys.version_info[0] < 3:
        infile = open(filename, 'rb')
    else:
        infile = open(filename, 'r', newline='', encoding='utf8')

    with infile as f:
        reader = csv.reader(f)

        # first header
        keys = next(reader)
        # store conference title from top left cell into schedule
        conference_title = keys[0].split('#')[0].strip()
        try:
            version = keys[0].split('#')[1].replace('Version', '').strip()
        except:
            pass
        last = keys[0] = 'meta'
        keys_uniq = []
        for i, k in enumerate(keys):
            if k != '':
                last = k.strip()
                keys_uniq.append(last)
            keys[i] = last

        # second header
        keys2 = next(reader)

        # data rows
        last = None
        for row in reader:
            i = 0
            items = OrderedDict([(k, OrderedDict()) for k in keys_uniq])
            row_iter = iter(row)

            for value in row_iter:
                value = value.strip()
                if keys2[i] != '' and value != '':
                    try:
                        items[keys[i]][keys2[i]] = value  # .decode('utf-8')
                    except AttributeError as e:
                        print("Error in row {}, cell {} value: {}".format(keys[i], keys2[i], value))
                        raise e
                i += 1

            try:
                start_time = tz.localize(datetime.strptime(
                    items['meta'][date] + ' ' + items['meta'].get(time, '12:00'),
                    date_format
                ))
                items['start_time'] = start_time
                items['end_time'] = start_time + default_talk_length

                # only accept valid entries
                if len(items['meta']) > 0 and title in items['meta']:
                    csv_schedule.append(items)

                    if min_date is None or start_time < min_date:
                        min_date = start_time
                    if max_date is None or start_time > max_date:
                        max_date = start_time

                    # check if end_time of previous event (calculated from default_talk_length) overlaps with start_time
                    # long term TODO: check also other events not only the previous one
                    if last is not None and last['end_time'] > start_time:
                        last['end_time'] = start_time
                    last = items
                else:
                    print(" ignoring empty/invalid row in CSV file")
            except RuntimeError as e:
                print(" ignoring row with invalid date in CSV file")
                print(e)

    if args.verbose:
        print(json.dumps(csv_schedule, indent=4, default=str))

    delta = max_date - min_date
    days_count = math.ceil(delta.days + (delta.seconds / 3600) / 24) + 1
    print(days_count, delta)

    schedule = Schedule.from_template(
        title=conference_title,
        acronym=acronym,
        year=min_date.year,
        month=min_date.month,
        day=min_date.day,
        days_count=days_count)
    schedule.schedule().version = '1.0' or version

    print(" converting to schedule ")

    for event in csv_schedule:
        id = str(base_id + int(event['meta']['ID']))
        guid = gen_uuid(hashlib.md5((acronym + id).encode('utf-8')).hexdigest())
        duration = (event['end_time'] - event['start_time']).seconds / 60

        if args.split_persons:
            event[persons] = event[persons].split(',')

        event_n = OrderedDict([
            ('id', id),
            ('guid', guid),
            # ('logo', None),
            ('date', event['start_time'].isoformat()),
            ('start', event['start_time'].strftime('%H:%M')),
            ('duration', '%d:%02d' % divmod(duration, 60)),
            ('room', event['meta'].get(room, 'Room')),
            ('slug', '-'.join([acronym, id, normalise_string(event['meta'][title])])),
            ('title', event['meta'][title]),
            ('subtitle', event['meta'].get('Untertitel', '')),
            ('track', ''),
            ('type', ''),
            ('language', event['meta'].get('Sprache', args.default_language)),
            ('abstract', ''),
            ('description', event['meta'].get(description, '')),
            ('do_not_record', event['meta'].get('Aufzeichnung?', '') == 'nein'),
            ('video_download_url', event['meta'].get('video_download_url')),
            ('persons', [OrderedDict([
                ('id', get_id(gen_uuid(p.strip().split('\n')[0]))),
                ('public_name', p.strip()),
                # ('#text', p),
            ]) for p in event[persons].values()]),
            ('links', [])
        ])

        if args.verbose:
            print(event_n['title'])
        try:
            schedule.add_event(Event(event_n))
        except Warning as e:
            print(e)

    print(" writing results to disk")
    schedule.export(acronym)


if __name__ == '__main__':
    main()
