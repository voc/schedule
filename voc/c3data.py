from os import getenv, path
import json
import git

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.exceptions import TransportQueryError

try:
    from .schedule import Schedule, Event
    from .tools import load_json, write, normalise_string

except ImportError:
    from schedule import Schedule, Event
    from tools import load_json, write


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
                'create': [{
                    'name': room,
                } for room in schedule.rooms()]
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


def add_room(conference_id, room_name):
    result = client.execute(gql('''
      mutation addRoom($input: UpsertRoomInput!) {
        upsertRoom(input: $input) {
          room { guid }
        }
      }'''), {'input': {'room': {
          'name': room_name,
          'conferenceId': conference_id
        }
    }})

    print(result)
    return result['upsertRoom']['room']['guid']


def add_event(conference_id, room_id, event):
    data = {
        "event": {
            **(event.graphql()),
            "conferenceId": conference_id,
            "roomId": room_id,
            "eventPeopleUsingGuid": {
                "create": [
                    {"personId": str(p['id']), "publicName": p['public_name']} for p in event['persons']
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
        '''), {'input': {'guid': event_guid}})
    except Exception as e:
        print(e)
        print()


class C3data:
    conference_id = None
    room_ids = {}

    def __init__(self, schedule: Schedule, create=False):
        result = create_conference(schedule) if create else get_conference(schedule.conference('acronym'))
        self.conference_id = result['conference']['id']
        self.room_ids = {x['name']: x['guid'] for x in result['conference']['rooms']['nodes']}

    def upsert_event(self, event):
        if event['room'] in self.room_ids:
            room_id = self.room_ids[event['room']]
        else:
            print('WARNING: Room {} does not exist, creating.'.format(event['room']))
            room_id = add_room(self.conference_id, event['room'])
            self.room_ids[event['room']] = room_id
        add_event(self.conference_id, room_id, Event(event))

    def depublish_event(self, event_guid):
        remove_event(event_guid)

    def process_changed_events(self, repo: git.Repo, options):
        changed_items = repo.index.diff('HEAD~1', 'events')
        for i in changed_items:
            write(i.change_type + ': ')
            try:
                if i.change_type == 'D':
                    event_guid = path.splitext(path.basename(i.a_path))[0]
                    self.depublish_event(event_guid)
                else:
                    event = load_json(i.a_path)
                    self.upsert_event(event)
            except Exception as e:
                print(e)
                if options.exit_when_exception_occours:
                    raise e


def push_schedule(schedule: Schedule, create=False):
    c3data = C3data(schedule, create)
    schedule.foreach_event(c3data.upsert_event)


def test():
    # schedule = Schedule.from_url('https://fahrplan.events.ccc.de/camp/2019/Fahrplan/schedule.json')
    schedule = Schedule.from_file('divoc/everything.schedule.json')
    # schedule = Schedule.from_file('rc3/everything.schedule.json')

    push_schedule(schedule)


if __name__ == '__main__':
    test()
    print('test done')
