from os import getenv
import json
import requests

try:
    from .schedule import Schedule
except ImportError:
    from schedule import Schedule

url = getenv('HUB_URL', 'https://api-test.rc3.cccv.de/api/c/rc3/')
conference_id = "17391cf3-fc95-4294-bc34-b8371c6d89b3"   # rc3 test

headers = {
    'Authorization': 'Token ' + getenv('HUB_TOKEN', 'XXXX'),
    'Accept': 'application/json'
}


def get(path):
    print('GET ' + url + path)
    r = requests.get(url + path, headers=headers)
    print(r.status_code)
    return r.json()


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
        raise Exception(r.json()['error'])
    return r


def upsert_event(event):
    if event['track']:
        if not(event['track'] in tracks):
            print('WARNING: Track {} does not exist'.format(event['track']))
            event['track'] = None

    # Workaround for bug in hub: remove empty room_id from dict
    if 'room_id' in event and not(event['room_id']) and 'room' in event:
        del event['room_id']

    post_event(event)


def depublish_event(event_guid):
    post_event({
        'guid': event_guid.event,
        'public': False
    })


skip = False
tracks = []


def init(channels):
    global tracks

    tracks = {x['name']: x['id'] for x in get('tracks')}


def push_schedule(schedule):
    channel_room_ids = {x['schedule_room']: x['room_guid'] for x in channels}
    rooms = get('rooms')
    room_ids = {x['name']: x['id'] for x in rooms}
    hub_room_names = {x['id']: x['name'] for x in rooms}

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
                    print('ERROR: Room {} does not exist'.format(event['room']))
                    return
            upsert_event(event)

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

    channels = requests \
        .get('https://c3voc.de/wiki/lib/exe/graphql2.php?query={channels{nodes{schedule_room,room_guid}}}') \
        .json()['data']['channels']['nodes']

    init(channels)

    schedule = Schedule.from_url('https://data.c3voc.de/rC3/everything.schedule.json')
    # schedule = Schedule.from_url('https://data.c3voc.de/rC3/channels.schedule.json')
    # schedule = Schedule.from_file('rC3/channels.schedule.json')
    
    push_schedule(schedule)
    print('done')
