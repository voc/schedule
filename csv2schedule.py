#!/usr/bin/python

# dependecies py-dateutil requests pytz
# deps for voc.tools lxml

# -*- coding: UTF-8 -*-
import requests
import json
from collections import OrderedDict
import dateutil.parser
from datetime import datetime
from datetime import timedelta
import csv
import hashlib
import sys
import os
import locale
import configparser

import voc.tools

# todo add proper logging
# todo add error handling
# todo make second out dir optional

config = configparser.ConfigParser()
config.read('config.conf')

reload(sys)
sys.setdefaultencoding('utf-8')

days = []
locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')


# config
offline = True and False  # todo => config

date_format = '%Y-%m-%d %H:%M'
output_dir = config['main']['output_dir']
secondary_output_dir = config['main']['secondary_output_dir']

# fill the template for the conference with conference information
template = {"schedule": OrderedDict([
    ("version", config['main']['version']),
    ("conference", OrderedDict([
        ("title", config['main']['title']),
        ("acronym", config['main']['acronym']),
        ("daysCount", int(config['main']['daysCount'])),  # todo calc this from date
        ("start", config['main']['start']),
        ("end", config['main']['end']),
        ("timeslot_duration", config['main']['timeslot_duration']),
        ("days", [])
    ]))
])
}

room_map = OrderedDict([
    (config['rooms']['room1'], 1)  # make this dynamic
])

if len(sys.argv) == 2:  # todo print a help message that people know whats this for
    output_dir = sys.argv[1]

if not os.path.exists(output_dir):  # todo this is unreadable => refactor
    if not os.path.exists(secondary_output_dir):
        os.mkdir(output_dir)  # todo handle exception
    else:
        output_dir = secondary_output_dir
        local = True
os.chdir(output_dir)  # todo handle exception


# todo this should be part of the template
def main():
    process(int(config['main']['id_offset']), config['main']['csv_url'])


def process(base_id, source_csv_url):
    ''' Process the CSV data into a json / xml suitable for frab schedule based applications '''

    global template, days
    out = template
    conference_start_date = dateutil.parser.parse(out['schedule']['conference']['start'])

    for i in range(out['schedule']['conference']['daysCount']):
        date = conference_start_date + timedelta(days=i)
        start = date + timedelta(hours=9)  # conference day starts at 11:00 # todo => config
        end = start + timedelta(hours=18)  # conference day lasts 17 hours # todo => config

        days.append(OrderedDict([
            ('index', i),
            ('date', date),
            ('start', start),
            ('end', end),
        ]))

        out['schedule']['conference']['days'].append(OrderedDict([
            ('index', i),
            ('date', date.strftime('%Y-%m-%d')),
            ('start', start.isoformat()),
            ('end', end.isoformat()),
            ('rooms', OrderedDict())
        ]))

    if not offline:
        ''' Get a remote csv file. This can be a google doc'''
        print(" Requesting schedule source url")

        # download schedule csv
        schedule_r = requests.get(
            source_csv_url,
            verify=True  # todo make a this config option
        )  # todo handle exception

        # make sure we work with utf-8
        schedule_r.encoding = 'utf-8'

        # todo this shout go into the exception handler also raising a exception that nobody catches is useless
        if schedule_r.ok is False:
            raise Exception(
                "Requesting schedule from CSV source url failed, HTTP code {0}.".format(schedule_r.status_code))

        # write the csv file to a file
        with open('schedule.csv', 'w') as f:
            f.write(schedule_r.text)

    csv_schedule = []  # csv data
    with open('schedule.csv', 'r') as f:
        reader = csv.reader(f)

        # first header
        keys = reader.next()
        #print('keys1' + str(keys))
        last = keys[0] = 'meta'
        keys_uniq = []
        for i, k in enumerate(keys):
            if k != '':
                last = k.strip()
                keys_uniq.append(last)
            keys[i] = last

        # second header
        keys2 = reader.next()
        #print('keys2' + str(keys2))

        # data rows
        for row in reader:
            i = 0
            items = OrderedDict([(k, OrderedDict()) for k in keys_uniq])
            row_iter = iter(row)

            for value in row_iter:
                value = value.strip()
                if keys2[i] != '' and value != '':
                    items[keys[i]][keys2[i]] = value.decode('utf-8')
                i += 1

            if items['meta'] and 'Title' in items['meta']:
                csv_schedule.append(items)

    if not csv_schedule:
        print("Error did not find any events in CSV")
        sys.exit(-1)

    for event in csv_schedule:
        meta = event['meta']
        #print(meta)  # debug
        event_id = str(base_id + int(meta.get('ID')))
        guid = voc.tools.gen_uuid(hashlib.md5(meta['Room'] + meta['ID']).hexdigest())
        start_time = datetime.strptime(meta['Date'] + ' ' + meta['Start'], date_format)
        duration = int(meta.get('Duration'))
        room = meta.get('Room', '')
        title = meta.get('Title')
        subtitle = meta.get('Subtitle', '')
        track = meta.get('Track', '')
        event_type = meta.get('Type', '')
        language = meta.get('Language')
        abstract = meta.get('Abstract', '')
        description = meta.get('Description', '')
	tmp_day = start_time - conference_start_date
	day = tmp_day.days + 1

        # check mandatory fields ( they should have no default above)
	
        mand = [event_id, guid, start_time, duration, title, language]
        for item in mand:
            if not item:
                print('ERROR: not all mandatory files could be found in the CSV ' + str(item))
		print('event_id: ' + str(event_id) + ' guid: ' + str(guid) + ' start_time: ' + str(start_time) + ' duration: ' + str(duration) + ' title: ' + title + ' language: ' + language)

        event_n = OrderedDict([
            ('id', event_id),
            ('guid', guid),
            # ('logo', None),
            ('date', start_time.isoformat()),
            ('start', start_time.strftime('%H:%M')),
            ('duration', '%d:%02d' % divmod(duration, 60)),
            ('room', room),
            ('slug', '-'.join([template['schedule']['conference']['acronym'], event_id,
                               voc.tools.normalise_string(meta.get('Title'))])
             ),
            ('title', title),
            ('subtitle', subtitle),
            ('track', track),
            ('type', event_type),
            ('language', language),
            ('abstract', abstract),
            ('description', description),
            ('persons', [OrderedDict([
                ('id', 0), # todo if no id supplied store generated per event in file to regenerate
                ('full_public_name', p.strip()),
            ]) for p in event['Speaker'].values()]),
            ('links', [])
        ])

        day_rooms = out['schedule']['conference']['days'][day-1]['rooms']
        if room not in day_rooms:
            day_rooms[room] = list()
        day_rooms[room].append(event_n)
	

    # write json schedule to file
    with open('schedule.json', 'w+') as fp:
        json.dump(out, fp, indent=4)
    
    # write xml schedule to file
    with open('schedule.xml', 'w') as fp:
        fp.write(voc.tools.dict_to_schedule_xml(out))

    print(' end')


if __name__ == '__main__':
    main()
