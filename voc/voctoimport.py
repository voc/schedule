from os import getenv
from sys import stdout
import json
import time
import argparse

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
# from gql.transport.exceptions import TransportQueryError

try:
    from .schedule import Schedule, Event
except ImportError:
    from schedule import Schedule, Event

transport = AIOHTTPTransport(
    url=getenv('IMPORT_URL', 'https://import.c3voc.de/graphql'),
    headers={'Authorization': getenv('IMPORT_TOKEN', 'Basic|Bearer|Token XXXX')}
)
client = Client(transport=transport, fetch_schema_from_transport=True)
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
        '''), {'input': {'guid': event_guid}})
    except Exception as e:
        print(e)
        print()


class VoctoImport:
    schedule = None
    conference = None

    def __init__(self, schedule: Schedule, create=False):
        global args

        self.schedule = schedule
        acronym = args.conference or args.acronym or schedule.conference('acronym')
        self.conference = get_conference(acronym)
        if not self.conference:
            raise Exception(f'Unknown conference {acronym}')
        pass

    def upsert_event(self, event):
        add_event(self.conference['id'], Event(event))

    def depublish_event(self, event_guid):
        remove_event(event_guid)


def push_schedule(schedule: Schedule, create=False):
    instace = VoctoImport(schedule, create)
    schedule.foreach_event(instace.upsert_event)


def run(args):
    if args.url or args.acronym:
        schedule = Schedule.from_url(
            args.url or f'https://pretalx.c3voc.de/{args.acronym}/schedule/export/schedule.json'
        )
    else:
        schedule = Schedule.from_file('jev22/channels.schedule.json')

    instace = VoctoImport(schedule)

    def upsert_event(event):
        if (len(args.room) == 0 or event['room'] in args.room) and event['do_not_record'] is not True:
            instace.upsert_event(event)

    try:
        schedule.foreach_event(upsert_event)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', action='store', help='url to schedule.json')
    parser.add_argument('--acronym', '-a', help='the conference acronym in pretalx.c3voc.de')
    parser.add_argument('--conference', '-c', help='the confence slug in import.c3voc.de')
    parser.add_argument('--room', '-r', action='append', help='filter rooms (multiple possible)')

    args = parser.parse_args()

    print(args)

    run(args)
    print('\nimport done')
