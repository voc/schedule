from os import getenv
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
      }'''), variable_values={'acronym': acronym})


def add_event(conference_slug, event):
    data = {
        "event": {
            'talkid': event['id'],
            'persons': ', '.join([p for p in event.persons()]),
            **(event.voctoimport()),
            'published': False,
            'conferenceToConferenceId': {
                'connectBySlug': {
                    'slug': conference_slug
                }
            }
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

    def __init__(self, schedule: Schedule, create=False):
        self.schedule = schedule
        pass

    def upsert_event(self, event):
        add_event(self.schedule.conference('acronym'), Event(event))

    def depublish_event(self, event_guid):
        remove_event(event_guid)


def push_schedule(schedule: Schedule, create=False):
    instace = VoctoImport(schedule, create)
    schedule.foreach_event(instace.upsert_event)


def test():
    schedule = Schedule.from_url('https://pretalx.c3voc.de/rc3-2021-haecksen/schedule/export/schedule.json')
    # schedule = Schedule.from_file('rc3/everything.schedule.json')

    try:
        push_schedule(schedule)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    test()
    print('test done')
