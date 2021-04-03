from os import getenv
import json

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.exceptions import TransportQueryError

from schedule import Schedule, Event

transport = AIOHTTPTransport(
    url=getenv('C3D_URL', 'https://data.c3voc.de/graphql'),
    headers={'Authorization': getenv('C3D_TOKEN', 'Basic|Bearer XXXX')}
)
# transport = AIOHTTPTransport(url="http://localhost:5001/graphql")

# Create a GraphQL client using the defined transport
client = Client(transport=transport, fetch_schema_from_transport=True)


def create_conference(schedule: Schedule):
    conference = schedule.conference()
    input = {
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
    #print(json.dumps(input, indent=2))

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
    '''), variable_values={'input': input})
        return result['createConference']

    except TransportQueryError as e:
        # raise exception, error is not 'conference already exists'
        if 'duplicate key value violates unique constraint "conferences_acronym_key"' != e.errors[0]['message']:
            raise e

        # conference already exists, so try to get required infos
        result = client.execute(gql('''
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
}'''), variable_values={
            'acronym': conference['acronym']
        })
        return result


def add_room(confernce_id, room_name):
    result = client.execute(gql('''
mutation addRoom($input: UpsertRoomInput!) {
  upsertRoom(input: $input) {
    room {
      guid
    }
  }
}'''), {'input': {
        'room': {
            'name': room_name,
            'conferenceId': confernce_id
        }}
    })

    print(result)
    return result['upsertRoom']['room']['guid']


def add_event(conference_id, room_id, event):
    input = {
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

    # print(str(query))
    try:
        client.execute(query, {'input': input})
    except Exception as e:
        print(json.dumps(input, indent=2))
        print()
        print(e)
        print()


def test():
    # schedule = Schedule.from_url('https://fahrplan.events.ccc.de/camp/2019/Fahrplan/schedule.json')
    schedule = Schedule.from_file('divoc/everything.schedule.json')
    # schedule = Schedule.from_file('rc3/everything.schedule.json')

    result = create_conference(schedule)
    conference_id = result['conference']['id']
    room_ids = {x['name']: x['guid'] for x in result['conference']['rooms']['nodes']}
    # print(room_ids)

    def process(event):
        if event['room'] in room_ids:
            room_id = room_ids[event['room']]
        else:
            print('WARNING: Room {} does not exist, creating.'.format(event['room']))
            room_id = add_room(conference_id, event['room'])
            room_ids[event['room']] = room_id
        add_event(conference_id, room_id, Event(event))

    schedule.foreach_event(process)


if __name__ == '__main__':
    test()
    print('test done')
