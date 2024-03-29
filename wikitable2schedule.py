# -*- coding: UTF-8 -*-
import os
import re
import json
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
debug = False
locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')

voc.tools.set_base_id(2000)

year = 2023
wiki_url = 'https://eh20.easterhegg.eu/self-organized-sessions?do=export_xhtml'
output_dir = "/srv/www/eh20"
secondary_output_dir = "./eh20"


template = {"schedule": {
    "version": "",
    "conference": {
        "acronym": "eh21",
        "title": "Easterhegg 21",
        "start": "2024-03-29",
        "end": "2024-04-02",
        "daysCount": 4,
        "timeslot_duration": "00:05",
        "time_zone_name": "Europe/Amsterdam",
        "rooms": [],
        "days": []
    }
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
    
    data = requests.get(wiki_url + '?do=export_xhtml').text if wiki_url.startswith('http') else open(wiki_url)
    soup = BeautifulSoup(data, 'html5lib')
    # soup = BeautifulSoup(data, 'lxml')

    # sections = soup.find_all('h3')
    elements = soup.select('h3, h2, table.inline')

    print('Processing sections')
    section_title = None
    room = None
    sections_to_ignore = [
        'durchgehende_treffpunkte_und_assemblies',
        'wochentag_datum',
        'regelmaessige_treffen',
        'raeume'
    ]
    for element in elements:
        if element.name == 'h3' or element.name == 'h2':
            section_title = element
            continue

        if element.name == 'h4':
            room = element.text
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
            event = process_row(row, tz, day, room, wiki_url)
            if event is not None:
                schedule.add_event(event)

    print()
    print()
    return schedule


def process_row(row, tz, day, room, wiki_url):
    event_n = None
    data = {}
    external_links = {}
    for td in row.find_all('td'):
        # if type(td) != NoneType:
        key = td.attrs['class'][0]
        data[key] = re.compile(r'\s*\n\s*').split(td.get_text().strip())
        external_links = voc.tools.parse_html_formatted_links(td)

    # ignore events which are already in pretalx
    '''
    if len(external_links) > 0:
        urls = external_links.keys()
        if list(urls)[0].startswith('https://cfp.eh20.easterhegg.eu/eh20/talk/'):
            return None
    '''
    
    try:
        time = re.compile(r'\s*(?:-|–)\s*').split(data['col0'][0])
        room = room or data['col1'][0]
        title = data['col2'][0]
        abstract = "\n".join(data['col3'][1:])
        persons, *links = data.get('col4', [None])

        '''
        	<tr class="row1">
                <td class="col0"> 10:00 - 11:00 </td>
                <td class="col1"> <a href="https://eh21.c3nav.de/l/k014/@0,395.51,91.4,3.39" class="urlextern" title="https://eh21.c3nav.de/l/k014/@0,395.51,91.4,3.39">K014</a> </td>
                <td class="col2 leftalign"> Chaos meets THW          </td>
                <td class="col3"> Wie funktioniert der Bevölkerungsschutz in .de und wie können sich Nerds im THW engagieren? </td>
                <td class="col4"> Dave (@laird_dave:matrix.cert.ccc.de) </td>
            </tr>
        '''

        if time == ['']:
            # ignore empty row
            return None

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

        duration = (end - start).total_seconds() / 60

        # ignore dummy events
        if duration == 0 or title == 'Beispielüberschrift' or persons == 'EH-Orga':
            return None

        guid = gen_uuid(f'{start}-{next(iter(links), title)}')
        local_id = voc.tools.get_id(guid)

        '''
        if 'Workshop3' in title or 'Workshop3' in abstract:
            room = 'Workshop 3'
        elif 'Workshop2' in title or 'Workshop2' in abstract:
            room = 'Workshop 2'
        elif 'Workshop' in title or 'Workshop' in abstract:
            room = 'Workshop 1'
        else:
            room = 'Self-organized'
        '''

        event = Event({
            'id': local_id,
            'guid': guid,
            # 'logo': None,
            'date': start.isoformat(),
            'start': start.strftime('%H:%M'),
            'duration': '%d:%02d' % divmod(duration, 60),
            'room': room or 'other',
            'slug': None,
            'url': wiki_url.split('?')[0],
            'title': title,
            'subtitle': '',
            'track': 'Workshop',
            'type': 'Workshop',
            'language': 'de',
            'abstract': abstract or '',
            'description': '',
            'persons': [{'id': 0, 'name': p.strip()} for p in persons and persons.split(',')],
            'links': [{'url': link_url, 'title': link_title} for link_url, link_title in external_links.items()]
        }, start)
        write('.')
        if debug:
            print(event)
        return event
    
    except ValueError as e:
        print(e)
        print(json.dumps(event_n, indent=2))

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
    import argparse
    import sys
    if len(sys.argv) == 2:
        output_dir = sys.argv[1]
    
    if not os.path.exists(output_dir):
        if not os.path.exists(secondary_output_dir):
            os.mkdir(output_dir)
        else:
            output_dir = secondary_output_dir
            local = True
    os.chdir(output_dir)
    
    parser = argparse.ArgumentParser()
    parser.add_argument('url', action="store", help="url to a wiki page containing a event table", default='')
    parser.add_argument('--create', action="store_true", default=False)
    args = parser.parse_args()
    
    schedule = fetch_schedule(args.url)
    schedule.export('wiki')

    if not local:
        os.system("git add *.json *.xml")
        os.system("git commit -m 'updates from " + str(datetime.now()) + "'")
        os.system("git push")

    print('')
    print('end')


if __name__ == '__main__':
    main()
