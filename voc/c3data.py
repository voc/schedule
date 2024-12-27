import argparse
from os import getenv, path
import json

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.exceptions import TransportQueryError

try:
    from .schedule import Schedule
    from .event import Event
    from .room import Room
    from .tools import load_json, write
    from . import logger


except ImportError:
    import sys
    sys.path.append('.')

    from schedule import Schedule, Event
    from room import Room
    from tools import load_json, write
    from voc import logger



transport = AIOHTTPTransport(
    url=getenv('C3D_URL', 'https://data.c3voc.de/graphql'),
    headers={'Authorization': getenv('C3D_TOKEN', 'Basic|Bearer XXXX')}
)
# transport = AIOHTTPTransport(url="http://localhost:5001/graphql")

# Create a GraphQL client using the defined transport
client = Client(transport=transport, fetch_schema_from_transport=True)


def create_conference(schedule: Schedule):
    conference = schedule.conference()
    data = {
        'conference': {
            'acronym': conference['acronym'],
            'title': conference['title'],
            'startDate': conference['start'],
            'endDate': conference['end'],
            'daysUsingId': {
                'create': [{
                    'index': day['index'],
                    'startDate': day['day_start'],
                    'endDate': day['day_end']
                } for day in schedule.days()]
            },
            'roomsUsingId': {
                'create': [room.graphql() for room in schedule.rooms(mode='obj')]
            }
        }
    }
    # print(json.dumps(data, indent=2))

    try:
        result = client.execute(gql('''
mutation createConferenceAndDaysAndRooms($input: CreateConferenceInput!) {
  createConference(input: $input) {
    conference {
      id
      rooms {
        nodes {
          guid
          slug
          name
        }
      }
    }
  }
}
    '''), variable_values={'input': data})
        return result['createConference']

    except TransportQueryError as e:
        # raise exception, error is not 'conference already exists'
        if 'duplicate key value violates unique constraint "conferences_acronym_key"' != e.errors[0]['message']:
            raise e

        # conference already exists, so try to get required infos
        result = get_conference(conference['acronym'])
        return result


def get_conference(acronym):
    return client.execute(gql('''
      query getConferenceAndRooms($acronym: String!) {
        conference: conferenceByAcronym(acronym: $acronym) {
          id
          rooms {
            nodes {
                guid
                name
            }
          }
        }
      }'''), variable_values={'acronym': acronym})


def add_room(conference_id, room: Room):
    result = client.execute(gql('''
      mutation addRoom($input: UpsertRoomInput!) {
        upsertRoom(input: $input) {
          room { guid, name, slug, meta }
        }
      }'''), {'input': {'room': {
        **room.graphql(),
        'conferenceId': conference_id
    }
    }})

    print(result)
    return result['upsertRoom']['room']['guid']


def add_event(conference_id, room_id, event: Event):
    data = {
        "event": {
            **(event.graphql()),
            "conferenceId": conference_id,
            "roomId": room_id,
            "eventPeopleUsingGuid": {
                "create": [
                    # TODO: add person guid
                    {"personId": str(p['id']), "publicName": p.get('name') or p.get('public_name')} for p in event['persons']
                ]}
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
        write('.')
        client.execute(query, {'input': data})
    except Exception as e:
        print(json.dumps(data, indent=2))
        print()
        print(e)
        print()


def remove_event(event_guid):
    try:
        client.execute(gql('''
          mutation deleteEvent($guid: UUID!) {
            deleteEvent(input: {guid: $guid}) { deletedEventNodeId }
          }
        '''), {'guid': event_guid})
    except Exception as e:
        print(e)
        print()


class C3data:
    conference_id = None
    room_ids = {}

    def __init__(self, schedule: Schedule, create=False):
        result = create_conference(schedule) if create else get_conference(schedule.conference('acronym'))
        if "errors" in result:
            logger.error(result['errors'])
        if not result['conference']:
            raise "Please create conference in target system using --create"
        self.conference_id = result['conference']['id']

        self.room_ids = {x['name']: x['guid'] for x in result['conference']['rooms']['nodes']}

        # check for new/updated rooms
        for room in schedule.rooms(mode='obj'):
            if room.name not in self.room_ids:
                room_id = add_room(self.conference_id, room)
                self.room_ids[room.name] = room_id

        # TODO check for new rooms and create them now

    def upsert_event(self, event: Event):
        if event['room'] in self.room_ids:
            room_id = self.room_ids[event['room']]
        else:
            print('WARNING: Room {} does not exist, creating.'.format(event['room']))
            room_id = add_room(self.conference_id, Room(name=event['room'], guid=event.get('room_id')))
            self.room_ids[event['room']] = room_id
        add_event(self.conference_id, room_id, event)

    def depublish_event(self, event_guid):
        remove_event(event_guid)

    def process_changed_events(self, repo: 'Repo', options):
        changed_items = repo.index.diff('HEAD~1', 'events')
        for i in changed_items:
            write(i.change_type + ': ')
            try:
                if i.change_type == 'D':
                    event_guid = path.splitext(path.basename(i.a_path))[0]
                    self.depublish_event(event_guid)
                else:
                    event = Event(load_json(i.a_path))
                    self.upsert_event(event)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(e)
                if options.exit_when_exception_occours:
                    raise e


def upsert_schedule(schedule: Schedule, create=False):
    c3data = C3data(schedule, create)
    try:
        schedule.foreach_event(c3data.upsert_event)
    except KeyboardInterrupt:
        pass


def test():
    # schedule = Schedule.from_url('https://fahrplan.events.ccc.de/camp/2019/Fahrplan/schedule.json')
    schedule = Schedule.from_file('38C3/everything.schedule.json')

    upsert_schedule(schedule, create=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('url', action="store", help="url or local path source schedule.json")
    parser.add_argument('--create', action="store_true", default=False)
    args = parser.parse_args()

    schedule = Schedule.from_url(args.url) if args.url.startswith('http') else Schedule.from_file(args.url)
    upsert_schedule(schedule, create=args.create)

    print('')
    print('done')
