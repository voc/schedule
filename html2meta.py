# -*- coding: UTF-8 -*-

from dataclasses import dataclass, field
from typing import List, Any
from bs4 import BeautifulSoup, Tag

import os
import sys
import json
import locale
import argparse
import requests
import pytz

locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')
tz = pytz.timezone("Europe/Amsterdam")

parser = argparse.ArgumentParser()
parser.add_argument('acronym', action="store", help="Series acronym, e.g. jev22")
parser.add_argument('--url', action="store", help="Source url, e.g. https://events.ccc.de/2022/11/28/dezentral-2022/", default='https://events.ccc.de/2022/11/28/dezentral-2022/')
parser.add_argument('-o', action="store", dest="output", help="output filename, e.g. current", default='current')
args = parser.parse_args()

acronym = args.acronym.lower()

@dataclass
class Location:
    id: str
    name: str
    region: str
    country: str
    description: dict[str, List[Tag]] = field(default_factory=lambda: {'Deutsch': [], 'English': []})
    infos: List[List[Any]] = field(default_factory=list)
    doc: List[Tag] = field(default_factory=list)

    def dict(self):
        return {
            'country': self.country,
            'region': self.region,
            'name': self.name,
            'id': self.id,
            'description': {
                'de': "\n".join([x for x in self.description['Deutsch']]),
                'en': "\n".join([x for x in self.description['English']]),
            },
            'infos': serialize_links(self.infos)
        }
    
    def __str__(self):
        # return str(self.dict())
        return json.dumps(self.dict(), indent=2, cls=SoupEncoder)


def serialize_links(infos):
    for x in infos:
        try:
            t, a = x
            return {"title": t.string.strip().strip(':'), "url": a['href']}
        except Exception as e:
            print(type(e).__name__)
            return ''.join([str(e) for e in x])
            

def fetch_post(source_url):
    print("Requesting source")

    conferences = []
    soup = BeautifulSoup(requests.get(source_url).text, 'html5lib')

    for chapter in soup.select('div.content > h2'):
        cid = chapter['id'].split('-')[3]
        print("\n==", cid, chapter.string)

        elements = chapter.find_next_siblings('h4')
        element = next(elements)

        while True:
            location = Location(
                id=element['id'],
                name=element.string,
                region=element.find_previous_sibling('h3'),
                country=cid
            )
            print("-", location.name)
            conferences.append(location)

            subsection = None
            for p in element.next_siblings:
                if p.name != 'p':
                    break

                if p.get('class') == ['subsection']:
                    subsection = p.string.strip()
                    continue

                if subsection == 'Info':
                    location.infos = [list(li.children) for li in p.select('li')]
                    continue

                if subsection and location:
                    location.description[subsection] += p.text.prettify()
                    continue

            element = next(elements)
            if not element or element.previous_sibling.name == 'h2':
                break

    return conferences
        

class SoupEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Location):
            return obj.dict()
        if isinstance(obj, Tag):
            return str(obj)
        return json.JSONEncoder.default(self, obj)


def main():
    data = fetch_post(args.url)

    with open("meta.json", "w") as fp:
        json.dump(data, fp, indent=2, cls=SoupEncoder)

    # schedule.export(args.output)

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
