#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import os
import re
import json
from datetime import datetime, timedelta
import locale
import traceback
import requests
from bs4 import BeautifulSoup, Tag

import voc.tools
from voc.tools import gen_uuid, write, Logger
from voc.schedule import Event, Schedule

log = Logger(__name__)
local = False
debug = False
locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')

voc.tools.set_base_id(200)

year = 2025
acronym = f'fediday{year}'
#source_de_url = 'https://berlinfedi.day/schedule/'
#source_en_url = 'https://berlinfedi.day/en/schedule/'

def main():
    global output_dir, secondary_output_dir, local, debug, year, acronym

    import argparse
    import sys

    output_dir = f"/srv/www/{acronym}"
    secondary_output_dir = f"./{acronym}"

    if len(sys.argv) == 2:
        output_dir = sys.argv[1]
    
    voc.tools.ensure_folders_exist(output_dir, secondary_output_dir)
    
    parser = argparse.ArgumentParser()
    parser.add_argument('acronym', action="store", help="Series acronym without year, e.g. `fediday`")
    parser.add_argument('year', action="store", help="Year, e.g. `2025`")
    parser.add_argument('--url', action="store", help="url to a page containing an <dl class=\"talkinfo\">", default='')
    parser.add_argument('--create', action="store_true", default=False)
    parser.add_argument('--debug', action="store_true", default=False)
    args = parser.parse_args()
    debug = args.debug

    schedule = fetch_schedule(args.url)
    schedule.export(acronym)

    print('')
    print('end')


def fetch_schedule(source_url):
    global template, days, tz

    r = requests.get(source_url) if source_url.startswith('http') else open(source_url)
    r.encoding = 'utf-8'
    soup = BeautifulSoup(r.text, 'html5lib')
    # soup = BeautifulSoup(data, 'lxml')
    head = soup.find('head')

    # Extract days from h2 elements
    #  <h2 id="freitag-3-oktober-2025-be-social">Freitag (3. Oktober 2025) <em>Be Social</em></h2>
    #  <h2 id="samstag-4-oktober-2025-the-fediverse-talks">Samstag (4. Oktober 2025) <em>The Fediverse Talks</em></h2>
    #  <h2 id="sonntag-5-oktober-2025-medien-im-fediverse">Sonntag (5. Oktober 2025) <em>Medien im Fediverse</em></h2>
    days = [{
        'date': datetime.strptime(re.search(r'(\d{1,2}\. \w+ \d{4})', day.get_text()).group(1), '%d. %B %Y'),
        'id': day.get('id'),
        'title': day.find('em').get_text(strip=True),
        'source': day
    } for day in soup.select('h2')]
    log.debug(f"Found days: {days}")


    schedule = Schedule(conference={
        "acronym": acronym,
        "title": head.find('title').get_text(strip=True),
        "description": head.find('meta', attrs={'property': 'og:description'})['content'],
        "start": days[0]['date'],
        "end": days[-1]['date'],
        "timeslot_duration": "00:05",
        "time_zone_name": "Europe/Amsterdam",
        "rooms": [],
        "days": []
    }, start_hour=9)

    print(f"Requesting events from {source_url}")

    elements = soup.select('div.scheduletablerow')
    for element in elements:
        event = process_row(element, days, schedule)
        if event is not None:
            print(f"Adding event {event['title']} at {event['date']} in room {event['room']}")
            schedule.add_event(event)

    print()
    print()
    return schedule


"""

process_row(…) takes following html snippet and returns an Event object

      <div class="scheduletablerow">
        <div class="scheduletablecell location1">
          <div class="scheduletablecellavatar">
            <a href="https://mastodon.social/@_elena"><img src="/elenarossini.jpg" class="speakeravatar"></a>
          </div>
          <div class="scheduletablecellinfo">
            <dl class="talkinfo">
              <dt>Titel</dt>
              <dd>The Future is federated (EN, DE)</dd>
              <dt>Redner_in</dt>
              <dd><a href="https://mastodon.social/@_elena">Elena Rossini</a><br />Italian filmmaker, photographer and
                writer, Paris</dd>
              <dt>Zeit / Ort</dt>
              <dd>12:10 / Mainhall</dd>
              <dt>Zusammenfassung</dt>
              <dd>
                <details>
                  <summary>Details</summary>
                  <p>
                    Eröffnet wird der Tag mit dem Film über das Fediverse von <a
                      href="https://mastodon.social/@_elena">@_elena@mastodon.social</a> (nur einer ihrer diverse
                    Account im Fediverse). Wir freuen uns sehr, euch als Premiere von ihrem Film <a
                      href="https://videos.elenarossini.com/w/64VuNCccZNrP4u9MfgbhkN">Introducing the Fediverse: a New
                      Era of Social Media</a>, mit deutscher Sprache zeigen zu dürfen. Elena lebt als Italienerin in
                    Paris. Sie erfreut uns mit Filmen, arbeitet als Fotografin und Autorin.
                  </p>
                </details>
              </dd>
            </dl>
          </div>
        </div>
      </div>

"""
def process_row(row, days, schedule):

    try:
        # TODO find day by h2 element
        dayElement = row.find_previous('h2')
        day: datetime = next((d['date'] for d in days if d['id'] == dayElement['id']), None)

        # Find the <dl class="talkinfo">
        dl = row.find('dl', class_='talkinfo')
        if not dl:
            return None
        dt_dd = list(dl.children)
        # Extract fields by iterating over dt/dd pairs
        title = None
        persons = None
        time_room = None
        abstract = ''
        links = []
        i = 0
        while i < len(dt_dd):
            el = dt_dd[i]
            if getattr(el, 'name', None) == 'dt':
                label = el.get_text(strip=True)
                # Find next dd
                j = i + 1
                while j < len(dt_dd) and getattr(dt_dd[j], 'name', None) != 'dd':
                    j += 1
                if j < len(dt_dd):
                    value = dt_dd[j]
                    if label == 'Titel':
                        title = value.get_text(strip=True)
                    elif label == 'Redner_in':
                        # Get speaker name and description
                        persons = value.get_text(" ", strip=True)
                        # Optionally, extract links from <a> tags
                        for a in value.find_all('a'):
                            links.append((a.get('href'), a.get_text(strip=True)))
                    elif label == 'Zeit / Ort':
                        time_room = value.get_text(strip=True)
                    elif label == 'Zusammenfassung':
                        # Try to get details/summary/paragraph
                        details = value.find('details')
                        if details:
                            # TODO how can we get HTML from a BeautifulSoup Tag?
                            abstract = details.find('p').get_text(" ", strip=True)
                        else:
                            abstract = value.get_text(" ", strip=True)
                i = j
            i += 1

        if not (title and time_room):
            log.debug("Missing title or time/room information")
            return None
        # Parse time and room
        # Example: '12:10 / Mainhall'
        time, room = None, None
        if '/' in time_room:
            time, room = [x.strip() for x in time_room.split('/', 1)]
        else:
            time = time_room.strip()
            room = room or 'other'

        # Compose datetime
        hour, minute = map(int, time.split(':'))
        start = schedule.localize(day.replace(hour=hour, minute=minute))
        end = start + timedelta(hours=1)  # Default duration 1h
        duration = (end - start).total_seconds() / 60

        guid = gen_uuid(f'{start}-{title}')
        local_id = voc.tools.get_id(guid)

        # Extract language from title if present in parentheses at the end
        lang = 'de'
        lang_match = re.search(r'\(([A-Za-z]{2})\)\s*$', title)
        if lang_match:
            lang = lang_match.group(1).lower()
            title = re.sub(r'\s*\([A-Za-z]{2}\)\s*$', '', title)

        event = Event({
            'id': local_id,
            'guid': guid,
            'date': start.isoformat(),
            'duration': f"{int(duration // 60)}:{int(duration % 60):02d}",
            'room': room or 'other',
            'url': '',
            'title': title,
            'subtitle': '',
            'track': '',
            'type': '',
            'language': lang,
            'abstract': abstract or '',
            'description': '',
            'persons': [{'id': 0, 'name': persons}] if persons else [],
            'links': [{'url': link_url, 'title': link_title} for link_url, link_title in links]
        }, start)
        write('.')
        if debug:
            print(event)
        return event
    except ValueError as e:
        print(e)
        # print(json.dumps(event, indent=2))
    except Exception as e:
        print(e)
        traceback.print_exc()
        # print(json.dumps(event, indent=2))
        print()


def process_person(soup: Tag):
    name = element.get_text(strip=True)
    uri = element.get('href')

dd = soup.find('dd')
link_tag = dd.find('a')

# Assign to variables
name = link_tag.get_text(strip=True)
profile_url = link_tag['href']
organization = dd.get_text(strip=True).replace(name, '', 1).strip()

    guid = gen_uuid(uri or name)
    person = {
        'guid': guid,
        'id': voc.tools.get_id(guid),
        'name': name,
        'org': None,
        #'links': [{'url': uri, 'title': name}] if uri else []
    }
    return person


def first(x):
    if len(x) == 0:
        return None
    else:
        return x[0]


if __name__ == '__main__':
    main()
