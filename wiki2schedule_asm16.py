 # -*- coding: UTF-8 -*-

import requests
import json
from collections import OrderedDict
import dateutil.parser
from datetime import datetime
from datetime import timedelta
import pytz
import os
import sys
import hashlib
import time
import locale

from bs4 import BeautifulSoup




reload(sys)
sys.setdefaultencoding('utf-8')

days = []
de_tz = pytz.timezone('Europe/Amsterdam')
#local = False
locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')

# some functions used in multiple files of this collection
import voc.tools

voc.tools.set_base_id(1000)


wiki_url = 'https://wiki.muc.ccc.de/asm:16:events-raw'
output_dir = "/srv/www/schedule/asm16"
secondary_output_dir = "./asm16"


template = { "schedule": {
        "version": "1.0",
        "conference": {
            "title": "ASM16",
            "daysCount": 4,
            "start": "2016-05-13",
            "end":   "2016-05-15",
            "timeslot_duration": "00:15",
            "days" : []
        },
    }
}



if len(sys.argv) == 2:
    output_dir = sys.argv[1]

if not os.path.exists(output_dir):
    if not os.path.exists(secondary_output_dir):
        os.mkdir(output_dir) 
    else:
        output_dir = secondary_output_dir
        local = True
os.chdir(output_dir)

room_map = OrderedDict([
    ('Hauptraum', 1),
    ('Draussen', 20),
    ('Labor', 2),
    ('Studio', 3),    
    ('Sprachschule 1', 11),
    ('Sprachschule 2', 12),
    ('Sprachschule 3', 13),
    ('Sprachschule 4', 14),
    ('Sprachschule 5', 15),
#    ('Lounge', 4)
])

def get_room_id(room_name):

    if room_name in room_map:
        return room_map[room_name]
    else:
        return 0

def get_track_id(track_name):
    return 10
            
            

def main():
    global wiki_url, template, days
    
    out = template
    
    conference_start_date = dateutil.parser.parse(out['schedule']['conference']['start'])
    
    for i in range(out['schedule']['conference']['daysCount']):
        date = conference_start_date + timedelta(days=i)
        start = date + timedelta(hours=11)     # conference day starts at 11:00
        end = start + timedelta(hours=17) # conference day lasts 17 hours
        
        days.append( OrderedDict([
            ('index', i),
            ('date' , date),
            ('start', start),
            ('end', end),
        ]))
        
        
        out['schedule']['conference']['days'].append(OrderedDict([
            ('index', i),
            ('date' , date.strftime('%Y-%m-%d')),
            ('start', start.isoformat()),
            ('end', end.isoformat()),
            ('rooms', OrderedDict())
        ]))
    
    # add rooms now, so they are in the correct order
    '''
    for day in out["schedule"]["conference"]["days"]:
        for key in room_map.keys():
            if key not in day['rooms']:
                day['rooms'][key] = list()
    
    '''
    
    print("Requesting wiki events")
    
    soup = BeautifulSoup(requests.get(wiki_url, verify=False).text, 'html5lib')
    table = soup.find('table', attrs={'class': 'inline'})
    table_body = table.find('tbody')
    rows = table_body.find_all('tr')

    # skip header row    
    rows_iter = iter(rows)
    next(rows_iter)

    for row in rows_iter:        
        event = {}
        for td in row.find_all('td'):
            #if type(td) != NoneType:
            key = td.attrs['class'][1]
            event[key] = td.get_text()
    
        
        guid = hashlib.md5(event['wo'] + event['wann'] + conference_start_date.isoformat() + event['titel']).hexdigest()   
        wann = time.strptime(event['wann'], "%A %H:%M")
        duration = event['dauer'].split(' ', 2)[0]

        # if duration is a approximation (e.g. '4-6 std') take  max value 
        if '-' in duration: 
            duration = duration.split('-')[1]
        # convert hours to minutes
        duration = int(duration)*60
        
        
        # event starts with Friday (day=0), which is wday 4
        day = 3 - wann.tm_wday

        start_time = days[day]['date'] + timedelta(hours=wann.tm_hour, minutes=wann.tm_min)
        end_time = start_time + timedelta(minutes=duration) 
  
        
        room = event['wo']

        event_n = OrderedDict([
            ('id', voc.tools.get_id(guid)),
            ('guid', guid),
            # ('logo', None),
            ('date', start_time.isoformat()),
            ('start', start_time.strftime('%H:%M')),
            ('duration', '%d:%02d' % divmod(duration, 60) ),
            ('room', room),
            ('slug', ''),
            #('slug', '31c3_-_6561_-_en_-_saal_1_-_201412271100_-_31c3_opening_event_-_erdgeist_-_geraldine_de_bastion',
            ('title', event['titel']),
            ('subtitle', ''),
            ('track', 'Workshop'),
            ('type', 'Workshop'),
            ('language', 'de' ),
            ('abstract', ''),
            ('description', '' ),
            ('persons', [ OrderedDict([
                ('id', 0),
                ('full_public_name', p.strip()),
                #('#text', p),
            ]) for p in event['workshopleiter'].split(',') ]),
            ('links', [])             
        ])
        
        day_rooms = out['schedule']['conference']['days'][day]['rooms']
        if room not in day_rooms:
            day_rooms[room] = []
        day_rooms[room].append(event_n)
    
        sys.stdout.write('.')
    
    #print json.dumps(out, indent=2)
    
    with open("schedule.json", "w") as fp:
        json.dump(out, fp, indent=4)
    
    
    with open('schedule.xml', 'w') as fp:
        fp.write(voc.tools.dict_to_schedule_xml(out))   

    # TODO only main + second + workshops + lounge
#    with open('halfnarp.json', 'w') as fp:
#        json.dump(schedule_to_halfnarp(out), fp, indent=4)
    
    print('')
    print('end')


if os.path.isfile("_sos_ids.json"):
    with open("_sos_ids.json", "r") as fp:
        #sos_ids = json.load(fp) 
        # maintain order from file
        temp = fp.read()
        sos_ids = json.JSONDecoder(object_pairs_hook=OrderedDict).decode(temp)
    
    next_id = max(sos_ids.itervalues())+1

def get_day(start_time):
    for day in days:
        if day['start'] <= start_time < day['end']:
            # print "Day {0}: day.start {1} <= start_time {2} < day.end {3}".format(day['index'], day['start'], start_time, day['end'])
            # print "Day {0}: day.start {1} <= start_time {2} < day.end {3}".format(day['index'], day['start'].strftime("%s"), start_time.strftime("%s"), day['end'].strftime("%s"))
            return day['index']
    
    print("  illegal start time: " + start_time.isoformat())   
    return None

def first(x):
    if len(x) == 0:
        return None
    else:
        return x[0]

if __name__ == '__main__':
    main()
    
#write sos_ids to disk
with open("_sos_ids.json", "w") as fp:
    json.dump(voc.tools.sos_ids, fp, indent=4)

if not local:  
    os.system("git add *.json *.xml")
    os.system("git commit -m 'updates from " + str(datetime.now()) +  "'")
    os.system("git push")
