from schedule import Schedule, Event
from os import getenv
import json
import requests
from slugify import slugify

url = getenv('HUB_URL', 'https://api-test.rc3.cccv.de/api/c/36c3/')
headers = {
    'Authorization': getenv('HUB_TOKEN', 'Token|Basic|Bearer XXXX'),
    'Accept': 'application/json'
}
#auth=(getenv('HUB_USER', 'andi'), getenv('HUB_PASSWORD', 'vocmucvocmuc'))
#conference_id = "4e21ff5f-b6f8-4711-9bd7-f7e4634b9cae"

url = 'http://127.0.0.1:8000/api/36c3/'
auth = ('andi', 'test1234')
conference_id = "159ace9f-1e37-448f-9c6a-afe96eaa5091"


def create(path, json):
    print('POST ' + url + path) # + ' (' + json['id'] + ')')
    r = requests.post(url + path, json=json, headers=headers)
    print(r.status_code)

    if r.status_code != 201:
        lines = r.text.split('\n', 3)
        print(lines[0])
        print(lines[1])

        raise Exception(r.status_code)
    # print(r.text)
    return r


def upsert(path, json):
    print('PUT ' + url + path)
    r = requests.put(url + path, json=json, headers=headers, allow_redirects=False)
    print(r.status_code)
    # print(r.text)
    return r


def get(path):
    print('GET ' + url + path)
    r = requests.get(url + path, headers=headers)
    print(r.status_code)
    #print(r.text)
    return r.json()


def create_conference(schedule: Schedule):
    conference = schedule.conference()

    for room in schedule.rooms():
        add_room(room)
    #print(json.dumps(input, indent=2))


def add_track(name):
    res = create('tracks', {
        "conference": conference_id,
        "slug": slugify(name),
        "name": name,
        "is_public": True
    })
    track = res.json()
    return track['id']


def add_room(room_name):
    res = create('assembly/main/rooms', {
        # "assembly_id": "098f9a12-5d30-45ba-ab52-f8d71a7a829f",
        "conference": conference_id,
        "name": room_name,
        "room_type": "lecturehall",
        "capacity": None,
        "links": []
    })

    room = res.json()
    return room['id']


def add_event(conference_id, room_id, event: Event):

    data = {
        "id": event['guid'],
        "kind": 'assembly',  #'official', # 'sos'
        #"assembly": 'MIGRATION',  
        "assembly": '1c395556-eeef-489f-bf5e-c8b32711f9b4',
        "room": room_id,
        "name": event['title'],
        "language": event['language'],
        "description": str(event['abstract']) + str(event['description']),
        "is_public": True,
        "schedule_start": event['date'],
        "schedule_duration":  event['duration'] + ':00',
        # "fsk": "all",
        "track": event['track_id'],
        "additional_data": event.meta()
    }
    # '''
    # try update first, if that fails create
    r2 = upsert('event/'+event['guid']+'/', data)
    if r2.status_code != 200 and r2.status_code != 301:
        lines = r2.text.split('\n', 3)
        print(lines[0])
        print(lines[1])

        r = create('events', data)
        if r.status_code != 201:
            print(json.dumps(data))
            lines = r.text.split('\n', 3)
            print(lines[0])
            print(lines[1])

            raise Exception(r.status_code)

    '''
  r = create('events', data)
  if r.status_code != 201:
    # try update
    r2 = upsert('event/'+event['guid']+'/', data)
    if r2.status_code != 200 and r2.status_code != 404:
      raise Exception(r2.text)
  #' ' '  
      "eventPeopleUsingGuid": { 
        "create": [
          {"personId": p['id'], "publicName": p['public_name']} for p in event['persons']
      ]}
    }
  }

  #print(str(query))
  try:
    client.execute(query, {'input': input})
  except Exception as e:
    print(json.dumps(input, indent=2))
    print()
    print(e)
    print() '''


skip = False


def test():
    #schedule = Schedule.from_url('https://fahrplan.events.ccc.de/camp/2019/Fahrplan/schedule.json')
    schedule = Schedule.from_file('36c3/everything.schedule.json')

    tracks = []

    #result = create_conference(schedule)
    #conference_id = result['conference']['id']
    room_ids = {x['name']: x['id'] for x in get('rooms')}
    tracks = {x['name']: x['id'] for x in get('tracks')}

    print(room_ids)
    print(tracks)

    def process(event):
        global skip
        if skip:
            if event['guid'] == skip:
                skip = False
            return

        if event['room'] in room_ids:
            room_id = room_ids[event['room']]
        else:
            print('WARNING: Room {} does not exist, creating.'.format(
                event['room']))
            room_id = add_room(event['room'])
            room_ids[event['room']] = room_id

        track_id = None
        if event['track']:
            if event['track'] in tracks:
                track_id = tracks[event['track']]
            else:
                print('WARNING: Track {} does not exist, creating.'.format(
                    event['track']))
                track_id = add_track(event['track'])
                tracks[event['track']] = track_id
        event['track_id'] = track_id

        add_event(conference_id, room_id, Event(event))

    schedule.foreach_event(process)


if __name__ == '__main__':
    import optparse
    parser = optparse.OptionParser()
    # , doc="Skips all events till event with guid X is found.")
    parser.add_option('--skip', action="store", dest="skip", default=False)

    options, args = parser.parse_args()
    skip = options.skip

    test()
    print('test done')
