from graphqlclient import GraphQLClient
from schedule import Schedule, Event
import json


#client = GraphQLClient('https://data.c3voc.de/graphql')
#client.inject_token('Basic XXXXXXX')
client = GraphQLClient('http://localhost:5001/graphql')



def create_conference(schedule: Schedule):
  conference = schedule.conference()
  input = {
    'conference': { 
      'acronym': conference['acronym'],
      'title': conference['title'],
      'startDate': conference['start'],
      'endDate': conference['end'],
      'daysUsingId': {
        'create': [ {
          'index': day['index'],
          'startDate': day['day_start'],
          'endDate': day['day_end']
        } for day in schedule.days() ]
      },
      'roomsUsingId': {
        'create': [ {
          'name': room,
        } for room in schedule.rooms() ]
      }
    }
  }
  print(json.dumps(input, indent=2))

  result = client.execute('''
    mutation createConferenceAndDays($input: CreateConferenceInput!) {
      createConference(input: $input) {
        conference {
          id
          rooms {
            nodes {
              id
              name
            }
          }
        }
      }
    }
  ''', {
    'input': input
  })

  if ( )



  print(result)
  return json.loads(result)['data']['createConference']

def add_room(confernce_id, room_name):
  result = client.execute('''
    mutation addRoom {
      upsertRoom {
        room {
          title
        }
      }
    }
  ''')

  print(result)

def add_event(confernece_id, room_id, event):
  input = {
    "event": {	
      **(event.graphql()),
      "conferenceId": confernece_id,
      "roomId": room_id,
      "eventPeopleUsingGuid": { 
        "create": [
          {"personId": p['id'], "publicName": p['public_name']} for p in event['persons']
      ]}
    }
  }
  #print(input)
  print()

  result = json.loads(client.execute('''
  mutation createEvent($input: CreateEventInput!) {
    __typename
    createEvent(input: $input) {
      clientMutationId
    }
  }''', {
    'input': input
  }))
  if 'errors' in result:
    print(input)
    print(json.dumps(result['errors'], indent=2))
  print()
  print()

def test():
  #schedule = Schedule.from_url('https://fahrplan.events.ccc.de/camp/2019/Fahrplan/schedule.json')
  schedule = Schedule.from_file('36C3/stages.schedule.json')

  result = create_conference(schedule)
  conference_id = result['conference']['id']
  room_ids = { x['name']: x['id'] for  x in result['conference']['rooms']['nodes'] }
  print(room_ids)

  def process(event: Event):
    room_id = int(room_ids[event['room']])
    add_event(conference_id, room_id, Event(event))

  schedule.foreach_event(process)


if __name__ == '__main__':
  test()