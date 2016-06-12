# -*- coding: UTF-8 -*-

import requests
import json
from collections import OrderedDict
import dateutil.parser
from datetime import datetime
from datetime import timedelta
import csv
import hashlib
import pytz
import sys, os
import locale


reload(sys)
sys.setdefaultencoding('utf-8')

days = []
de_tz = pytz.timezone('Europe/Amsterdam')
#local = False
locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')

# some functions used in multiple files of this collection
import voc.tools

#config
offline = True and False

date_format = '%Y-%m-%d %H:%M'
output_dir = '/srv/www/schedule/jh16'
secondary_output_dir = "./jh16"


template = { "schedule":  OrderedDict([
        ("version", "1.1"),
        ("conference",  OrderedDict([
            ("title", "Jugend Hackt 2016"),
            ("acronym", "jh16"),
            ("daysCount", 3),
            ("start", "2016-06-10"),
            ("end",   "2016-06-12"),
            ("timeslot_duration", "00:10"),
            ("days", [])
        ]))
    ])
}

room_map = OrderedDict([
    ('Süd', 1)
])

def get_room_id(room_name):
    if room_name in room_map:
        return room_map[room_name]
    else:
        return 0

def get_track_id(track_name):
    return 10
            


if len(sys.argv) == 2:
    output_dir = sys.argv[1]

if not os.path.exists(output_dir):
    if not os.path.exists(secondary_output_dir):
        os.mkdir(output_dir) 
    else:
        output_dir = secondary_output_dir
        local = True
os.chdir(output_dir)



def main():
    
    # source_csv_url = 'https://docs.google.com/spreadsheets/d/1maNYpcrD1RHCCCD1HyemuUS5tN6FG6bdHJZr3qv-V1w/export?format=csv&id=1maNYpcrD1RHCCCD1HyemuUS5tN6FG6bdHJZr3qv-V1w&gid=0'

    process('sued', 1000, 'https://docs.google.com/spreadsheets/d/XXX/export?format=csv')
    process('nord', 2000, 'https://docs.google.com/spreadsheets/d/XXX/export?format=csv')
    process('west', 3000, 'https://docs.google.com/spreadsheets/d/XXX/export?format=csv')



def process(ort, base_id, source_csv_url):
    global template, days
    
    out = template
    
    
    print('Processing ' + ort)
    
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
        

    
    
    if not offline:
        print("Requesting schedule source url") # , e.g. BER or Sendezentrum
        schedule_r = requests.get(
            source_csv_url, 
            verify=False #'cacert.pem'
        )
        
        # don't ask me why google docs announces by header? it will send latin1 and sends utf8...
        schedule_r.encoding = 'utf-8'
        
        if schedule_r.ok is False:
            raise Exception("  Requesting schedule from CSV source url failed, HTTP code {0}.".format(schedule_r.status_code))
        
        with open('schedule-' + ort + '.csv', 'w') as f:
            f.write(schedule_r.text)

    
    csv_schedule = []
    with open('schedule-' + ort + '.csv', 'r') as f:
        reader = csv.reader(f)
        
        # first header
        keys = reader.next()
        last = keys[0] = 'meta'
        keys_uniq = []
        for i, k in enumerate(keys):
            if k != '': 
                last = k.strip()
                keys_uniq.append(last)
            keys[i] = last
        
        # second header
        keys2 = reader.next()

        # data rows
        for row in reader:
            i = 0
            items = OrderedDict([ (k, OrderedDict()) for k in keys_uniq ])
            row_iter = iter(row)
            
            for value in row_iter:
                value = value.strip()
                if keys2[i] != '' and value != '':
                    items[keys[i]][keys2[i]] = value.decode('utf-8')
                i += 1
            
            if len(items['meta']) > 0 and 'Projektname' in items['meta']:
                csv_schedule.append(items)       
    
    #print json.dumps(csv_schedule, indent=4) 
    
    for event in csv_schedule:         
                
        #guid =  voc.tools.gen_uuid(room + event['meta']['Projektname'])
        #guid = voc.tools.gen_random_uuid()
        
        start_time = datetime.strptime( event['meta']['Datum'] + ' ' + event['meta']['Uhrzeit'], date_format)
        # TODO use start_time of next event as end_time
        end_time   = start_time + timedelta(minutes=3) 
        duration   = (end_time - start_time).seconds/60
        
        ## Chaos Communication Congress always starts at the 27th which is day 1
        ## Maybe TODO: Use days[0]['start'] instead
        #day = int(start_time.strftime('%d')) - 26
        
        # event starts with Friday (day=0), which is wday 4
        day = 3 #TODO
        id = base_id + int(event['meta']['ID'])
        room = event['meta']['Ort']
        guid = voc.tools.gen_uuid(hashlib.md5(ort + room + event['meta']['ID']).hexdigest())

        
        event_n = OrderedDict([
            ('id', id),
            ('guid', guid),
            # ('logo', None),
            ('date', start_time.isoformat()),
            ('start', start_time.strftime('%H:%M')),
            #('duration', str(timedelta(minutes=event['Has duration'][0])) ),
            ('duration', '%d:%02d' % divmod(duration, 60) ),
            ('room', room),
            ('slug', 'jh16-' + id ),
            ('title', event['meta']['Projektname']),
            ('subtitle', ''),
            ('track', ''),
            ('type', ''),
            ('language', 'de' ),
            ('abstract', ''),
            ('description', '' ),
            ('persons', [ OrderedDict([
                ('id', 0),
                ('full_public_name', p.strip()),
                #('#text', p),
            ]) for p in event['TeilnehmerInnen'].values() ]),
            ('links', [])             
        ])
        
        #print event_n['title']
        
        day_rooms = out['schedule']['conference']['days'][day-1]['rooms']
        if room not in day_rooms:
            day_rooms[room] = list();
        day_rooms[room].append(event_n);
        
        
    
    #print json.dumps(schedule, indent=2)
    
    with open('schedule-' + ort + '.json', 'w') as fp:
        json.dump(out, fp, indent=4)
        
    with open('schedule-' + ort + '.xml', 'w') as fp:
        fp.write(voc.tools.dict_to_schedule_xml(out));
            
    print 'end'
    


if __name__ == '__main__':
    main()
