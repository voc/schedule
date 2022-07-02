#!/usr/bin/env python3
import argparse
from collections import OrderedDict
from datetime import datetime
import voc.tools
from voc.schedule import Schedule
from urllib.parse import quote_plus


parser = argparse.ArgumentParser()
parser.add_argument('file', action="store", help="path to input.json")
# parser.add_argument('-o', action="store", dest="output", help="output filename, e.g. events.wiki")
args = parser.parse_args()


def to_wiki(event):
    h, m = event['duration'].split(':', 2)
    duration = int(h) * 60 + int(m)

    wiki = '{{Event \n' + ("|Has subtitle={subtitle}\n|Has start time={startdate} \n" +
                    "|Has duration={duration} \n|Has session location=Room:{room}\n|GUID={guid}\n").format(
        subtitle=event['title'],
        startdate=datetime.strptime(event['date'], '%Y-%m-%dT%H:%M:%S').strftime('%Y/%m/%d %H:%M'),
        duration=duration,
        room=event['room'],
        guid=event['guid']
    ) + '}}'
    print(wiki)


def main(args):
    schedule = Schedule.from_file(args.file)

    lang_map = {
        'de': 'de - German',
        'en': 'en - English'
    }

    event = {}
    event['title'] = "DLF"
    pagename = quote_plus(event['title'].replace(' ', '_'))
    print("\n")
    print('https://events.ccc.de/congress/2017/wiki/index.php/Session:{}?action=edit'.format(pagename))

    wiki = '{{Session \n' + ("|Is for kids=No\n|Has description={text}\n|Has session type={type}\n" +
                        "|Is organized by={persons}\n|Held in language={lang}\n|Has orga contact=\n").format(
            text=event['title'],
            type='',
            persons='',
            lang = lang_map['de']
    ) + '}}\n'
    print(wiki)

    schedule.foreach_event(to_wiki)


if __name__ == '__main__':
    main(args)
