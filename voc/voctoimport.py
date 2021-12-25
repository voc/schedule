from os import getenv
from sys import stdout
import json
import time

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
# from gql.transport.exceptions import TransportQueryError

try:
    from .schedule import Schedule, Event
except ImportError:
    from schedule import Schedule, Event

transport = AIOHTTPTransport(
    url=getenv('C3D_URL', 'https://import.c3voc.de/graphql'),
    headers={'Authorization': getenv('IMPORT_TOKEN', 'Basic|Bearer|Token XXXX')}
)
# Create a GraphQL client using the defined transport
client = Client(transport=transport, fetch_schema_from_transport=True)


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
        self.schedule = schedule
        self.conference = get_conference(schedule.conference('acronym'))
        pass

    def upsert_event(self, event):
        add_event(self.conference['id'], Event(event))

    def depublish_event(self, event_guid):
        remove_event(event_guid)


def push_schedule(schedule: Schedule, create=False):
    instace = VoctoImport(schedule, create)
    schedule.foreach_event(instace.upsert_event)


def test():
    schedule = Schedule.from_url('https://pretalx.c3voc.de/rc3-2021-chaoszone/schedule/export/schedule.json')
    # schedule = Schedule.from_file('rc3/everything.schedule.json')

    try:
        push_schedule(schedule)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    test()
    print('\nimport done')
