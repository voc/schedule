# -*- coding: UTF-8 -*-
import os
import re
import sys
import json
from collections import OrderedDict
from datetime import datetime, timedelta
import locale
import traceback
import requests
from bs4 import BeautifulSoup

import voc.tools
from voc.tools import gen_uuid, write
from voc.schedule import Event, Schedule

days = []
local = False
locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')

voc.tools.set_base_id(2000)

year = 2022
wiki_url = 'https://di.c3voc.de/sessions-liste?do=export_xhtml#liste_der_self-organized_sessions'
output_dir = "/srv/www/divoc"
secondary_output_dir = "./divoc"


template = {"schedule": {
    "version": "1.0",
    "conference": {
        "title": "DiVOC Bridging Bubbles",
        "acronym": "divoc_bb3",
        "daysCount": 4,
        "start": "2022-04-15",
        "end":   "2022-04-18",
        "timeslot_duration": "00:15",
        "time_zone_name": "Europe/Amsterdam",
        "days": [],
        "base_url": "https://di.c3voc.de/",
    },
}}


def get_track_id(track_name):
    return 10


def fetch_schedule(wiki_url):
    global template, days, tz

    # TODO refactor schedule class, to allow more generic templates

    schedule = Schedule.from_dict(template, start_hour=9)
    tz = schedule.tz()
    conference_start_date = tz.localize(schedule.conference_start())
    
    print("Requesting wiki events")
    
    soup = BeautifulSoup(requests.get(wiki_url).text, 'html5lib')
    # soup = BeautifulSoup(open("divoc-sessions.xhtml"), 'lxml')

    # sections = soup.find_all('h3')
    elements = soup.select('h3, h2, table.inline')

    print('Processing sections')
    section_title = None
    sections_to_ignore = [
        'durchgehende_treffpunkte_und_assemblies',
        'wochentag_datum',
        'regelmaessige_treffen'
    ]
    for element in elements:
        if element.name == 'h3' or element.name == 'h2':
            section_title = element
            continue

        # ignore some sections
        if element.name == 'table':
            if section_title.attrs['id'] in sections_to_ignore:
                continue

        #print(section_title.text)
        day = section_title.text.split(',')[1].strip()
        day_dt = tz.localize(datetime.strptime(day, '%d.%m.%Y'))

        # ignore sections which are not in target time span
        if day_dt < conference_start_date:
            print(' ignoring ' + section_title.text)
            continue

        rows = element.find_all('tr')

        # skip header row
        rows_iter = iter(rows)
        next(rows_iter)

        for row in rows_iter:
            event = process_row(row, tz, day)
            if event is not None:
                schedule.add_event(event)
 
    # print(json.dumps(out, indent=2))
    print()
    print()
    return schedule


def process_row(row, tz, day):
    event_n = None
    data = {}
    external_links = {}
    for td in row.find_all('td'):
        # if type(td) != NoneType:
        key = td.attrs['class'][0]
        data[key] = re.compile(r'\s*\n\s*').split(td.get_text().strip())
        external_links = voc.tools.parse_html_formatted_links(td)
    
    try:
        time = re.compile(r'\s*(?:-|–)\s*').split(data['col0'][0])
        title = data['col1'][0]
        abstract = "\n".join(data['col1'][1:])
        persons, *links = data.get('col2', [None])

        if time == ['00:00', '24:00']:
            print('\n ignore 24h event: {}'.format(title))
            return None
        start = tz.localize(datetime.strptime(day + ' ' + time[0], '%d.%m.%Y %H:%M'))
        try:
            end = tz.localize(datetime.strptime(day + ' ' + time[1], '%d.%m.%Y %H:%M'))
        except IndexError:
            print(f'\n end time is missing, assuming duration of 2h for event: {title}')
            end = start + timedelta(hours=2)
        except ValueError:
            print(f'\n end time {time[1]} is invalid, assuming duration of 2h for event: {title}')
            end = start + timedelta(hours=2)

        guid = gen_uuid('{}-{}'.format(start, next(iter(links), title)))
        local_id = voc.tools.get_id(guid)
        duration = (end - start).total_seconds() / 60

        if 'Workshop3' in title or 'Workshop3' in abstract:
            room = 'Workshop 3'
        elif 'Workshop2' in title or 'Workshop2' in abstract:
            room = 'Workshop 2'
        elif 'Workshop' in title or 'Workshop' in abstract:
            room = 'Workshop 1'
        else:
            room = 'Self-organized'

        event = Event(OrderedDict([
            ('id', local_id),
            ('guid', guid),
            # ('logo', None),
            ('date', start.isoformat()),
            ('start', start.strftime('%H:%M')),
            ('duration', '%d:%02d' % divmod(duration, 60)),
            ('room', room),
            ('slug', None),
            ('url', wiki_url.split('?')[0]),
            ('title', title),
            ('subtitle', ''),
            ('track', 'Workshop'),
            ('type', 'Workshop'),
            ('language', 'de'),
            ('abstract', abstract or ''),
            ('description', ''),
            ('persons', [OrderedDict([
                ('id', 0),
                ('public_name', p.strip()),
                # ('#text', p),
            ]) for p in persons and persons.split(',')]),
            ('links', [ 
                {'url': link_url, 'title': link_title} for link_url, link_title in external_links.items()
            ])
        ]), start)
        write('.')
        return event

    except Exception as e:
        print(e)
        traceback.print_exc()
        print(data)
        print(json.dumps(event_n, indent=2))
        print()


def first(x):
    if len(x) == 0:
        return None
    else:
        return x[0]


def main():
    schedule = fetch_schedule(wiki_url)
    schedule.export('wiki')

    print('')
    print('end')


if __name__ == '__main__':
    if len(sys.argv) == 2:
        output_dir = sys.argv[1]

    if not os.path.exists(output_dir):
        if not os.path.exists(secondary_output_dir):
            os.mkdir(output_dir) 
        else:
            output_dir = secondary_output_dir
            local = True
    os.chdir(output_dir)

    main()

    if not local:  
        os.system("git add *.json *.xml")
        os.system("git commit -m 'updates from " + str(datetime.now()) + "'")
        os.system("git push")
