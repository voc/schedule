#!/usr/bin/env python3

from os import getenv
from sys import stdout
import json
import time
import argparse
import requests
import base64
import uuid

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
# from gql.transport.exceptions import TransportQueryError

try:
    from .schedule import Schedule
    from .schedulexml import ScheduleXML
    from .tools import gen_uuid, normalise_string


except ImportError:
    from schedule import Schedule
    from schedulexml import ScheduleXML
    from tools import gen_uuid, normalise_string


transport = AIOHTTPTransport(
    url=getenv('IMPORT_URL', 'https://import.c3voc.de/graphql'),
    headers={'Authorization': getenv('IMPORT_TOKEN', 'Basic|Bearer|Token XXXX')}
)
# Disable schema fetching to avoid frozen dataclass issue with Python 3.13+
client = Client(transport=transport, fetch_schema_from_transport=False)

DEFAULT_LANGUAGE = 'de'

args: argparse.Namespace

def get_conference(acronym):
    return client.execute(gql('''
      query getConference($acronym: String!) {
        conference: conferenceBySlug(slug: $acronym) {
          id
          slug
          title
        }
      }'''), variable_values={'acronym': acronym})['conference']


'''
CREATE TABLE event_event (
    guid uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    talkid integer NOT NULL UNIQUE,
    slug character varying(140) NOT NULL,
    title character varying(200) NOT NULL,
    subtitle character varying(200),
    abstract text NOT NULL,
    description text NOT NULL,
    date timestamp with time zone NOT NULL,
    duration character varying(5) NOT NULL,
    language character varying(10) NOT NULL,
    persons text NOT NULL,
    room character varying(100) NOT NULL,
    track character varying(100),
    url character varying(200) NOT NULL,
    published boolean NOT NULL DEFAULT false,
    conference_id integer NOT NULL REFERENCES event_conference(id) DEFERRABLE INITIALLY DEFERRED,
    videofile character varying(1000),
    remotevideofile character varying(200)
);
'''

def add_event(conference, event, args):

    # TODO: use voc.tools or make this configurable e.g. based on conference year
    voc_slug = f"{conference['slug']}-{event['id']}-{event['slug'] \
        if (not(args.overwrite_slug) and event.get('slug', None)) else normalise_string(event['title'])[:50]}"
    #voc_slug = f"fossgis{event['slug']}"
    #assert event['slug'], "slug required"

    url = event.url()
    # Check if url returns 200
    try:
        response = requests.head(url, timeout=5)
        if response.status_code != 200:
            print(f"\n Warning: URL {url} returned status code {response.status_code}")
    except Exception as e:
        print(f"\n Warning: Could not verify URL {url}: {e}")

    guid = event['guid']
    if not guid:
        guid = gen_uuid(voc_slug)
    else:
        # Check if guid is a valid UUID
        try:
            uuid.UUID(guid)
        except ValueError:
            print(f"\n Warning: GUID {guid} is not a UUID in standard serialisation")

            # Try to decoded an compact Base64 UUID format (22 chars, URL-safe)
            # we have to add some padding because Python's base64 decoder
            padded = guid + "=" * (-len(guid) % 4)
            raw = base64.urlsafe_b64decode(padded)

            if len(raw) == 16:
                guid = str(uuid.UUID(bytes=raw))
                print(f"Converted input GUID to UUID: {guid}")
            else:
                raise ValueError("Decoded value is not 16 bytes")

    data = {
        "event": {
            'guid': guid,
            'talkid': int(event['id']),
            'slug': voc_slug,
            'title': event['title'],
            'subtitle': (event.get('subtitle') or '')[:200] or None,
            'abstract': event.get('abstract') or '',
            'description': event.get('description') or '',
            'date': event['date'],
            'duration': event['duration'],
            'language': event['language'] or DEFAULT_LANGUAGE,
            'room': event['room'],
            'track': event.get('track', None),
            'url': url,
            'persons': '\n'.join([p for p in event.persons()]),
            # 'published': False, -> defaults to false
            'conferenceId': conference['id'],
        }
    }

    query = gql('''
      mutation upsertEvent($input: UpsertEventInput!) {
        upsertEvent(input: $input) {
          clientMutationId
        }
      }
    ''')

    try:
        client.execute(query, variable_values={'input': data})
        stdout.write('.')
        stdout.flush()
    except Exception as e:
        print(json.dumps(data, indent=2))
        print()
        print(e)
        print()
        time.sleep(10)


def remove_event(event_guid):
    try:
        client.execute(gql('''
          mutation deleteEvent($guid: UUID!) {
            deleteEvent(input: {guid: $guid}) { deletedEventNodeId }
          }
        '''), variable_values={'guid': event_guid})
    except Exception as e:
        print(e)
        print()


class VoctoImport:
    schedule = None
    conference = None

    def __init__(self, schedule: Schedule|ScheduleXML, create=False):
        global args

        self.schedule = schedule
        acronym = (args.conference if args else None) \
            or getattr(args, 'acronym', None) \
            or schedule.conference('acronym')
        self.conference = get_conference(acronym)
        if not self.conference:
            raise Exception(f'Unknown conference {acronym}')
        pass

    def upsert_event(self, event, args):
        add_event(self.conference, event, args)

    def depublish_event(self, event_guid):
        remove_event(event_guid)


def push_schedule(schedule: Schedule, create=False):
    instace = VoctoImport(schedule, create)
    schedule.foreach_event(lambda event: instace.upsert_event(event, args))


def run(args: argparse.Namespace):
    schedule: Schedule|ScheduleXML
    
    if args.file is not None:
        path = args.file
        schedule = ScheduleXML.from_file(path) if path.endswith('.xml') else Schedule.from_file(path)
    else:
        url =  args.url or f'https://pretalx.c3voc.de/{args.acronym or args.conference}/schedule/export/schedule.json'
        schedule = ScheduleXML.from_url(url) if url.endswith('.xml') else Schedule.from_url(url)

    instace = VoctoImport(schedule)

    def upsert_event(event):
        if (len(args.room) == 0 or event['room'] in args.room) and event['do_not_record'] is not True:
            instace.upsert_event(event, args)

    try:

        if args.id or args.guid:
            for event in schedule.events():
                if (args.id and event['id'] in args.id) or (args.guid and event['guid'] in args.guid):
                    upsert_event(event)
        
        else:
            schedule.foreach_event(upsert_event)

        print('\nimport done')

    except KeyboardInterrupt:
        print('\nimport aborted by user')
        pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--conference', '-c', required=True, help='the confence slug in import.c3voc.de')

    # choose one of these
    parser.add_argument('--url', action='store', help='url to schedule.json/xml')
    parser.add_argument('--file', action='store', help='path to schedule.json/schedule.xml')
    parser.add_argument('--acronym', '-a', help='the conference acronym in pretalx.c3voc.de')

    # other
    parser.add_argument('--room', '-r', action='append', help='optional: filter rooms (multiple possible)', default=[])
    parser.add_argument('--year', '-y', help='the year of the conference')
    parser.add_argument('--id', action='append', help='filter to a specific event ID')
    parser.add_argument('--guid', action='append', help='filter to a specific event GUID')

    # optional flags
    parser.add_argument('--overwrite-slug', help='rebuild slug form title', action='store_true', default=False)

    if getenv('IMPORT_TOKEN') is None:
        print('WARNING: no IMPORT_TOKEN environment variable set, but required for write access')
        print('Set IMPORT_TOKEN to a valid token to avoid this warning')

    args = parser.parse_args()
    run(args)
