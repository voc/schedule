# -*- coding: UTF-8 -*-

import json
from collections import OrderedDict
import dateutil.parser
from datetime import timedelta
import time
import locale
import csv
import hashlib
import os


# some functions used in multiple files of this collection
import voc.tools
#from voc.tools import *

voc.tools.set_base_id(1000)
days = []
locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')

#config
offline = False

input_filename = 'camp99.csv'

header = """ 
{ 
  "schedule": {
    "version": "1.2",
    "conference": {
      "title": "Chaos Comunication Camp 1999",
      "start": "1999-08-06",
      "end": "1999-08-08",
      "daysCount": 3,
      "timeslot_duration": "00:05",
      "days": []
    }
  }
}
"""

#input:
#   filename.csv
#output:
#   filename.schedule.json
#   filename.schedule.xml


def csv2schedule(csv_file, header):
        
    print 'Building schedule header'
    
    schedule = json.JSONDecoder(object_pairs_hook=OrderedDict).decode(header)
    conference_start_date = dateutil.parser.parse(schedule['schedule']['conference']['start'])
    
    for i in xrange(schedule['schedule']['conference']['daysCount']):
        date = conference_start_date + timedelta(days=i)
        start = date + timedelta(hours=11)     # conference day starts at 11:00
        end = start+timedelta(hours=17) # conference day lasts 17 hours
        days.append( OrderedDict([
            ('index', i),
            ('date' , date),
            ('start', start ),
            ('end', end),
        ]))
        schedule['schedule']['conference']['days'].append(OrderedDict([
            ('index', i),
            ('date' , date.strftime('%Y-%m-%d')),
            ('start', start.isoformat()),
            ('end', end.isoformat()),
            ('rooms', OrderedDict())
        ]))
    

    print 'Processing' 
    
    csv_schedule = []
    output_filename = os.path.splitext(csv_file)[0]
    
    with open(csv_file, 'rb') as f:
        reader = csv.reader(f)
        keys = reader.next()
        
        # if name of the first column is empty, name it 0
        if keys[0] == '':
            keys[0] = '0'
        
        for row in reader:
            i = 0
            items = {}
            for value in row:
                items[keys[i].strip()] = value.strip().decode('utf-8')
                i += 1
            csv_schedule.append(items)       
    
    
    for event in csv_schedule:        
        guid = hashlib.md5(event['room'] + event['day'] + event['start_hour']).hexdigest()     
        
        wday = time.strptime(event['day'], '%A').tm_wday
        # event starts with Friday (day=0), which is wday 4
        day = 4-wday
        
        room = event['room']
        
        start_time = days[day]['date'] + timedelta(hours=int(event['start_hour'])) 
        end_time = start_time + timedelta(hours=1.5) 
        duration = (end_time - start_time).seconds/60
        
        event_n = OrderedDict([
            ('id', voc.tools.get_id(guid)),
            ('guid', guid),
            # ('logo', None),
            ('date', start_time.isoformat()),
            ('start', start_time.strftime('%H:%M')),
            ('duration', '%d:%02d' % divmod(duration, 60) ),
            ('room', room),
            ('slug', ''),
            ('title', event['title']),
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
            ]) for p in event['persons'].split(',') ]),
            ('links', [])             
        ])
        
        #print event_n['title']
        
        day_rooms = schedule['schedule']['conference']['days'][day]['rooms']
        if room not in day_rooms:
            day_rooms[room] = []
        day_rooms[room].append(event_n)
        
        
    
    #print json.dumps(schedule, indent=2)
    
    with open(output_filename + '.schedule.json', 'w') as fp:
        json.dump(schedule, fp, indent=4)

    with open(output_filename + '.schedule.xml', 'w') as fp:
        fp.write(voc.tools.dict_to_schedule_xml(schedule));
            
    print 'end'

if __name__ == '__main__':
    csv2schedule(input_filename, header)
