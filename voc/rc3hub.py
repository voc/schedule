from schedule import Schedule
from os import getenv
import json
import requests
from slugify import slugify

url = getenv('HUB_URL', 'https://api-test.rc3.cccv.de/api/c/rc3/')
conference_id = "17391cf3-fc95-4294-bc34-b8371c6d89b3"   # rc3 test

headers = {
    'Authorization': 'Token ' + getenv('HUB_TOKEN', 'XXXX'),
    'Accept': 'application/json'
}

def post_event(event):
    print('POST {}event/{}/schedule'.format(url, event['guid']))
    r = requests.post(
        '{}event/{}/schedule'.format(url, event['guid']),
        json=event, 
        headers=headers
    )
    print(r.status_code)

    if r.status_code != 201:
        print(json.dumps(event, indent=2))
        lines = r.text.split('\n', 3)
        print(lines[0:2])
        raise Exception(r.status_code)
    return r


def create(path, body):
    print('POST ' + url + path) 
    r = requests.post(url + path, json=body, headers=headers)
    print(r.status_code)

    if r.status_code != 201:
        print(json.dumps(body))
        lines = r.text.split('\n', 3)
        print(lines[0:2])
        raise Exception(r.status_code)
    # print(r.text)
    return r


def update(path, body):
    print('PUT ' + url + path)
    r = requests.put(url + path, json=body, headers=headers, allow_redirects=False)
    print(r.status_code)
    return r


def get(path):
    print('GET ' + url + path)
    r = requests.get(url + path, headers=headers)
    print(r.status_code)
    return r.json()


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
    # add new rooms to Assembly 'incomming', can be sorted later...
    res = create('assembly/incoming/rooms', {
        # "assembly_id": "098f9a12-5d30-45ba-ab52-f8d71a7a829f",
        "conference": conference_id,
        "name": room_name,
        "room_type": "stage",
        "capacity": None,
        "links": []
    })

    room = res.json()
    return room['id']

skip = False

channels = requests \
    .get('https://c3voc.de/wiki/lib/exe/graphql2.php?query={channels{nodes{name:schedule_room,id:room_guid}}}') \
    .json()['data']['channels']['nodes']


def full_sync():
    schedule = Schedule.from_url('https://data.c3voc.de/rC3/everything.schedule.json')

    #schedule = Schedule.from_url('https://data.c3voc.de/rC3/channels.schedule.json')
    #schedule = Schedule.from_file('rC3/channels.schedule.json')

    tracks = []
    channel_room_ids = {x['name']: x['id'] for x in channels}
    rooms = get('rooms')
    room_ids = {x['name']: x['id'] for x in rooms}
    hub_room_names = {x['id']: x['name'] for x in rooms}

    tracks = {x['name']: x['id'] for x in get('tracks')}

    print(tracks)

    def process(event):
        global skip
        if skip:
            if event['guid'] == skip:
                skip = False
            return

        try: 
            if event['room'] in channel_room_ids:
                event['room_id'] = channel_room_ids.get(event['room'])
                del event['room']
            elif not(event['room'] in room_ids):
                if event['room'] in channel_room_ids:
                    try:
                        event['room'] = hub_room_names[channel_room_ids[event['room']]]
                    except Exception as e:
                        print(json.dumps(event, indent=2))
                        print(e.message)
                else:
                    print('WARNING: Room {} does not exist'.format(event['room']))
                    return

            if event['track']:
                if not(event['track'] in tracks):
                    print('WARNING: Track {} does not exist'.format(event['track']))
                    event['track'] = None

            post_event(event)
        except Exception as e:
            print(json.dumps(event, indent=2))
            print(event['guid'])
            print(e)

    schedule.foreach_event(process)


if __name__ == '__main__':
    import optparse
    parser = optparse.OptionParser()
    # , doc="Skips all events till event with guid X is found.")
    parser.add_option('--skip', action="store", dest="skip", default=False)

    options, args = parser.parse_args()
    skip = options.skip

    full_sync()
    print('done')
