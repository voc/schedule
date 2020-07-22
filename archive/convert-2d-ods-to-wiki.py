#!/usr/bin/env python3
import argparse
from collections import OrderedDict
from datetime import datetime
import re
import uuid
#import voc.tools


parser = argparse.ArgumentParser()
parser.add_argument('file', action="store", help="path to input.ods")
parser.add_argument('-s', action="store", dest="sheet", help="Sheet name", default="Sheet1")
#parser.add_argument('-o', action="store", dest="output", help="output filename, e.g. events.wiki")
args = parser.parse_args()


from pyexcel_ods3 import get_data
data = get_data(args.file)[args.sheet]
header = data[1]

events = []
for i in range(len(header)):
    events.append(OrderedDict())

total_duration = 0

d = enumerate(data)
next(d) # skip empty row
next(d) # skip header
for i, row in d:
    # skip empty rows
    if not row:
        continue
    r = enumerate(row)

    timespan = row[0]
    start, sh, sm, end, eh, em = re.match("((\d+)h(\d*))[^\d]+((\d+)h(\d*))", timespan).groups()

    # when minute empty: fall back to 0
    sm = 0 if not sm else int(sm)
    em = 0 if not em else int(em)

    dummy, time = next(r) # skip first column
    for day, text in r:
        if text != '':
            #TODO when *h=0 or 1 or 2... add additional +1 to day

            startdate = "2017/12/{day} {h}:{m:02d}".format(day=26 + day, h=sh, m=sm)
            start_time = datetime.strptime(startdate, '%Y/%m/%d %H:%M')
            enddate = "2017/12/{day} {h}:{m:02d}".format(day=26 + day, h=eh, m=em)
            end_time = datetime.strptime(enddate, '%Y/%m/%d %H:%M')

            events[day][start] = {
                'startdate': startdate,
                'timespan': timespan,
                'start_time': start_time,
                'end_time': end_time,
                'text': text
            }


# fix end_time's for multi-row cells
for day, items in enumerate(events):
    last = None
    for start, event in items.items():

        if last is not None \
                and event['start_time'] > last['end_time'] \
                and last['end_time'] != event['start_time']:
            print(last)
            print(event)
            print()
            last['end_time'] = event['start_time']

        last = event


for day, items in enumerate(events):
    for start, event in items.items():
        duration = int((event['end_time'] - event['start_time']).seconds / 60)

        total_duration += duration

        #print(day, time, text)
        #startime = datetime.strptime(start, '%Hh%m')

        wiki =  '{{' + ("Event \n|Has subtitle={text} \n|Has start time={startdate} \n" +
            "|Has duration={duration} \n|Has session location={room}\n|GUID={guid}\n").format(
            text=event['text'],
            startdate=event['startdate'],
            duration=duration,
            room="Room:Hall 3",
            guid=uuid.uuid4()
        ) + '}}'
        print(wiki)


print("Total duration: {0}".format(total_duration/60))
