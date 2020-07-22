#!/usr/bin/env python3
import argparse
from collections import OrderedDict
from datetime import datetime
import re
import uuid
#import voc.tools
import csv
import json


parser = argparse.ArgumentParser()
parser.add_argument('file', action="store", help="path to input.ods")
##parser.add_argument('-o', action="store", dest="output", help="output filename, e.g. events.wiki")
args = parser.parse_args()


filename = "KoMoNa.csv"

infile = open(args.file, 'r', newline='', encoding='utf8')

events = None

with infile as f:
    reader = csv.reader(f)

    # first header
    keys = next(reader)
    last = None
    keys[0] = ''
    keys_uniq = []
    for i, k in enumerate(keys):
        if k != '':
            last = k.strip()
            keys_uniq.append(last)
        keys[i] = last

    events = OrderedDict([(k, OrderedDict()) for k in keys_uniq])

    # second header
    keys2 = next(reader)
    rooms = []
    rooms_uniq = []
    for i in keys2:
        # only the first word of the second header is the room name
        name = i.split(' ')[0]
        rooms.append(name)
        if name != '' and name not in rooms_uniq:
                rooms_uniq.append(name)

    events = OrderedDict([(k, OrderedDict()) for k in keys_uniq])
    for day in keys_uniq:
        for room in rooms_uniq:
            events[day][room] = OrderedDict()

    #print(json.dumps(events, indent=4) )

    # data rows
    last = None
    for row in reader:
        i = 0

        row_iter = iter(row)

        timespan = row[0]
        next(row_iter)

        if timespan is '':
            continue
        start, end = timespan.split(' ')

        for text in row_iter:
            text = text.strip()
            if keys[i] and rooms[i] != '' and text != '':
                try:
                    #                 MI 27.12.
                    ''''
                    match = re.match(".+(\d+)\.d+\.", keys[i])
                    if not match:
                        print("Error – no match!")
                        print(keys[i])
                        print(re)

                    mday = match.groups()
                    '''
                    mday = keys[i].split(' ')[1].split('.')[0]


                    startdate = "2017/12/{day} {h}:{m:02d}".format(day=mday, h=start, m=0)
                    start_time = datetime.strptime(startdate, '%Y/%m/%d %H:%M')
                    enddate = "2017/12/{day} {h}:{m:02d}".format(day=mday, h=end, m=0)
                    end_time = datetime.strptime(enddate, '%Y/%m/%d %H:%M')

                    duration = int((end_time - start_time).seconds / 60)

                    events[keys[i]][rooms[i]][timespan] = {
                        'startdate': startdate,
                        'duration': duration,
                        #'timespan': timespan,
                        #'start_time': start_time,
                        #'end_time': end_time,
                        'text': text
                    }



                except AttributeError as e:
                    print(text)
                    print("Error in day {}, room {}, {} : {}".format(keys[i], rooms[i], timespan, text))
                    #print(json.dumps(events, indent=4))
                    #raise e
            i += 1


#print(json.dumps(events, indent=4))


total_duration = 0

room_map = {
    'AQUA': 'Room:Komona Aquarius',
    'BIKINI': 'Room:Komona Blue Princess',
    'CORAL': 'Room:Komona Coral Reef',
    'D.RESS': 'Room:Komona D.Ressrosa'
}


for day, rooms in events.items():
    #print(day)
    for room, events in rooms.items():
        #print(room)
        for timespan, event in events.items():
            total_duration += event['duration']
            print()
            print()
            pagename = event['text'].replace(' ', '_').replace('&', '')
            print('https://events.ccc.de/congress/2017/wiki/index.php/Session:{}?action=edit'.format(pagename))

            wiki = '{{' + ("Session \n|Is for kids=No\n|Has description={text}\n|Has session type={type}\n|Is organized by=\n|Held in language=en - English, de - German\n|Has orga contact=\n".format(
                type='Workshop', text=event['text'])
            ) + '}}\n'

            wiki +=  '{{' + ("Event \n|Has subtitle= \n|Has start time={startdate} \n" +
                "|Has duration={duration} \n|Has session location={room}\n|GUID={guid}\n").format(
                text=event['text'],
                startdate=event['startdate'],
                duration=event['duration'],
                room=room_map[room],
                guid=uuid.uuid4()
            ) + '}}'
            print(wiki)


print("Total duration: {0}".format(total_duration/60))
