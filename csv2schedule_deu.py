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

#begin config
offline = True # and False

acronym = 'mm17'
default_talk_length = timedelta(minutes=30)
# source_csv_url = 'https://docs.google.com/spreadsheets/d/1maNYpcrD1RHCCCD1HyemuUS5tN6FG6bdHJZr3qv-V1w/export?format=csv&id=1maNYpcrD1RHCCCD1HyemuUS5tN6FG6bdHJZr3qv-V1w&gid=0

#end config


date_format = '%Y-%m-%d %H:%M'


template = { "schedule":  OrderedDict([
        ("version", "1.0"),
        ("conference",  OrderedDict([
            ("title", ""), 
            ("acronym", acronym),
            ("daysCount", 2),
            ("start", "2017-05-06"),
            ("end",   "2017-05-07"),
            ("timeslot_duration", "00:15"),
            ("days", [])
        ]))
    ])
}

output_dir = '/srv/www/schedule/' + acronym
secondary_output_dir = "./{}/".format(acronym)

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
    process(acronym, 0, source_csv_file)

def process(ort, base_id, source_csv_url):
    global template, days
    
    out = template
    
    
    print('Processing ' + ort)
    
    conference_start_date = dateutil.parser.parse(out['schedule']['conference']['start'])
    
    for i in range(out['schedule']['conference']['daysCount']):
        date = conference_start_date + timedelta(days=i)
        start = date + timedelta(hours=11) # conference day starts at 11:00
        end = start + timedelta(hours=17)  # conference day lasts 17 hours
        
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
        print(" Requesting schedule source url")
        schedule_r = requests.get(
            source_csv_url, 
            verify=False #'cacert.pem'
        )
        
        # don't ask me why google docs announces by header? it will send latin1 and then sends utf8...
        schedule_r.encoding = 'utf-8'
        
        if schedule_r.ok is False:
            raise Exception("  Requesting schedule from CSV source url failed, HTTP code {0}.".format(schedule_r.status_code))
        
        with open('schedule-' + ort + '.csv', 'w') as f:
            f.write(schedule_r.text)

    
    csv_schedule = []
        reader = csv.reader(f)
    with open('schedule-' + ort + '.csv', 'r') as f:
        
        # first header
        keys = reader.next()
        # store conference title from top left cell into schedule
        out['schedule']['conference']['title'] = keys[0]
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
            
            if len(items['meta']) > 0 and 'Titel' in items['meta']:
                csv_schedule.append(items)       
    
    #print json.dumps(csv_schedule, indent=4) 
    
    for event in csv_schedule:
        start_time = datetime.strptime( event['meta']['Datum'] + ' ' + event['meta']['Uhrzeit'], date_format)
        # TODO check if start_time of next (or other) event overlaps with end_time calculated from default_talk_length
        end_time   = start_time + default_talk_length 
        duration   = (end_time - start_time).seconds/60
        
        id = str(base_id + int(event['meta']['ID']))
        room = event['meta']['Ort']
        guid = voc.tools.gen_uuid(hashlib.md5(ort + room + id).hexdigest())
        
        event_n = OrderedDict([
            ('id', id),
            ('guid', guid),
            # ('logo', None),
            ('date', start_time.isoformat()),
            ('start', start_time.strftime('%H:%M')),
            ('duration', '%d:%02d' % divmod(duration, 60) ),
            ('room', room),
            ('slug', '-'.join([acronym, id, voc.tools.normalise_string(event['meta']['Titel'])])
            ),
            ('title', event['meta']['Titel']),
            ('subtitle', event['meta'].get('Untertitel', '')),
            ('track', ''),
            ('type', ''),
            ('language', 'de' ),
            ('abstract', ''),
            ('description', event['meta'].get('Beschreibung', '') ),
            ('persons', [ OrderedDict([
                ('id', 0),
                ('full_public_name', p.strip()),
                #('#text', p),
            ]) for p in event['Vortragende'].values() ]),
            ('links', [])             
        ])
        
        #print event_n['title']
        
        tmp_day = start_time - conference_start_date
        day = tmp_day.days + 1
        
        day_rooms = out['schedule']['conference']['days'][day-1]['rooms']
        if room not in day_rooms:
            day_rooms[room] = list();
        day_rooms[room].append(event_n);
        
        
    
    #print json.dumps(schedule, indent=2)
    
    with open('schedule-' + ort + '.json', 'w') as fp:
        json.dump(out, fp, indent=4)
        
    with open('schedule-' + ort + '.xml', 'w') as fp:
        fp.write(voc.tools.dict_to_schedule_xml(out));
            
    # TODO: Validate XML via schema file
    print(' end')
    


if __name__ == '__main__':
    main()
