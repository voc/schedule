#!/usr/bin/env python3
import argparse
import json
from collections import OrderedDict
from datetime import datetime
from urllib.parse import quote_plus
from voc.schedule import Schedule
import voc.tools

parser = argparse.ArgumentParser()
parser.add_argument('file', action="store", help="path to input.ods")
# parser.add_argument('-o', action="store", dest="output", help="output filename, e.g. events.wiki")
args = parser.parse_args()

schedule = Schedule.from_file(args.file)

lang_map = {
    'de': 'de - German',
    'en': 'en - English'
}


def to_wiki(event):
    pagename = quote_plus(event['title'].replace(' ', '_'))
    print('https://events.ccc.de/congress/2017/wiki/index.php/Session:{}?action=edit'.format(pagename))

    persons = ', '.join([p['full_public_name'] for p in event['persons']])
    wiki = '{{Session \n|' + \
        f"Is for kids=No\n|Has description={event['description']}\n" + \
        f"|Has session type={event['type']}\n|Is organized by={persons}\n" + \
        f"|Held in language={lang_map[event['language']]}\n|Has orga contact=\n" + \
        '}}\n'

    h, m = event['duration'].split(':', 2)
    duration = int(h) * 60 + int(m)
    start = datetime.strptime(event['date'], '%Y-%m-%dT%H:%M:%S').strftime('%Y/%m/%d %H:%M')

    wiki += '{{Event \n' + \
        f"|Has subtitle={event['subtitle']}\n|Has start time={start} \n" + \
        f"|Has duration={duration} \n" + \
        f"|Has session location=Room:{event['room']}\n|GUID={event['guid']}\n"
    + '}}'
    print(wiki)

    print("\n\n")


voc.tools.foreach_event(schedule, to_wiki)
