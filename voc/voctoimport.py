#!/usr/bin/env python3

from os import getenv
from sys import stdout
import json
import time
import argparse

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
args = None


def get_conference(acronym):
    return client.execute(gql('''
      query getConference($acronym: String!) {
        conference: conferenceBySlug(slug: $acronym) {
          id
          title
        }
      }'''), variable_values={'acronym': acronym})['conference']


def add_event(conference_id, event):
    data = {
        "event": {
            'talkid': event['id'],
            'persons': ', '.join([p for p in event.persons()]),
            **(event.voctoimport()),
            'abstract': event.get('abstract') or '',
            'published': False,
            'conferenceId': conference_id
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
        client.execute(query, {'input': data})
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
        acronym = args.conference or getattr(args, 'acronym', None) or schedule.conference('acronym')
        self.conference = get_conference(acronym)
        if not self.conference:
            raise Exception(f'Unknown conference {acronym}')
        pass

    def upsert_event(self, event):
        add_event(self.conference, event)

    def depublish_event(self, event_guid):
        remove_event(event_guid)


def push_schedule(schedule: Schedule, create=False):
    instace = VoctoImport(schedule, create)
    schedule.foreach_event(instace.upsert_event)


def run(args):
    if args.url or args.acronym:
        url =  args.url or f'https://pretalx.c3voc.de/{args.acronym}/schedule/export/schedule.json'
        schedule = ScheduleXML.from_url(url) if url.endswith('.xml') else Schedule.from_file(url)
    else:
        path = args.file
        schedule = ScheduleXML.from_file(path) if path.endswith('.xml') else Schedule.from_file(path)

    instace = VoctoImport(schedule)

    def upsert_event(event):
        if (len(args.room) == 0 or event['room'] in args.room) and event['do_not_record'] is not True:
            instace.upsert_event(event)

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


    args = parser.parse_args()

    print(args)

    run(args)
