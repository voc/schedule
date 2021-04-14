# -*- coding: UTF-8 -*-

import os
import sys
from collections import OrderedDict
from datetime import datetime
import locale
import argparse
import requests
import pytz
from bs4 import BeautifulSoup

import voc.tools
from voc.schedule import Schedule, Event

locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')
tz = pytz.timezone("Europe/Amsterdam")

parser = argparse.ArgumentParser()
parser.add_argument('acronym', action="store", help="Series acronym, e.g. cadusdebate")
parser.add_argument('--title', action="store", help="Series title, e.g. CADUS Debate!", default='CADUS Debate!')
parser.add_argument('--url', action="store", help="Source url, e.g. https://cadus.org/debate", default='https://cadus.org/debate')
parser.add_argument('-o', action="store", dest="output", help="output filename, e.g. current", default='current')
args = parser.parse_args()

acronym = args.acronym.lower()

def fetch_schedule(series_title, source_url):
    print("Requesting source")

    soup = BeautifulSoup(requests.get(source_url).text, 'html5lib')

    infobox = soup.select('div.info-box > p')
    date = infobox[0].get_text().replace('Start', '')
    # https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes
    start = tz.localize(datetime.strptime(date, '%A %d.%m.%Y %H:%M'))
    duration = 2 * 60

    schedule = Schedule.from_template(
        title=series_title,
        acronym=acronym,
        year=start.year,
        month=start.month,
        day=start.day)
    schedule.schedule().version = '1.0'

    guid = voc.tools.gen_uuid('{}-{}'.format(start, acronym))
    local_id = (start.year - 2020) * 100 + start.month
    title = soup.select('h2')[0].text
    abstract = None
    body = soup.select('div.ce_rs_column_start > div.ce_text.block > p')[0]
    persons = []
    external_links = voc.tools.parse_html_formatted_links(body)

    print("Found event on {} with title '{}'".format(start, title))

    schedule.add_event(Event(OrderedDict([
        ('id', local_id),
        ('guid', guid),
        # ('logo', None),
        ('date', start.isoformat()),
        ('start', start.strftime('%H:%M')),
        ('duration', '%d:%02d' % divmod(duration, 60)),
        ('room', 'Saal 23'),
        ('slug', '{slug}-{id}-{name}'.format(
            slug=acronym,
            id=local_id,
            name=voc.tools.normalise_string(title.lower())
        )),
        ('url', source_url),
        ('title', title),
        ('subtitle', ''),
        ('track', None),
        ('type', None),
        ('language', 'de'),
        ('abstract', abstract or ''),
        ('description', str(body)),
        ('persons', [OrderedDict([
            ('id', 0),
            ('public_name', p.strip()),
            # ('#text', p),
        ]) for p in persons]),
        ('links', [
            {'url': link_url, 'title': link_title} for link_url, link_title in external_links.items()
        ])
    ])))

    return schedule


def main():

    schedule = fetch_schedule(args.title, args.url)
    schedule.export(args.output)

    print('')
    print('end')


if __name__ == '__main__':
    output_dir = "/srv/www/" + acronym
    secondary_output_dir = "./" + acronym

    if len(sys.argv) == 2:
        output_dir = sys.argv[1]

    if not os.path.exists(output_dir):
        if not os.path.exists(secondary_output_dir):
            os.mkdir(output_dir)
        else:
            output_dir = secondary_output_dir
    os.chdir(output_dir)

    main()
