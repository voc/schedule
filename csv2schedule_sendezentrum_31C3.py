# -*- coding: UTF-8 -*-

import requests
import json
from collections import OrderedDict
import dateutil.parser
from datetime import datetime
from datetime import timedelta
import csv
import hashlib


# some functions used in multiple files of this collection
import voc.tools

voc.tools.set_base_id(1000)
days = []

#config
offline = False
date_format = '%d/%m/%y %I:%M %p'


def main():
        
    print 'Requesting schedule'
    
    if offline:
        with open('schedule.json') as file:
            schedule_json = file.read()
        full_schedule = json.JSONDecoder(object_pairs_hook=OrderedDict).decode(schedule_json)
    
    else:
        schedule_r = requests.get(
            'https://events.ccc.de/congress/2014/Fahrplan/schedule.json', 
            verify=False #'cacert.pem'
        ) 
        # we use ordered dicts, to maintain the order of all elements
        # this also improves diffs of the input and output files       
        full_schedule = json.JSONDecoder(object_pairs_hook=OrderedDict).decode(schedule_r.text)

    
    
    schedule = voc.tools.copy_base_structure(full_schedule, 5);
    
    for day in full_schedule['schedule']['conference']['days']:
        days.append({
            'index' : day['index'],
            'data' : day['date'],
            'start': dateutil.parser.parse(day['day_start']),
            'end': dateutil.parser.parse(day['day_end']),
        })
    

    print 'Processing' 
    
    csv_schedule = []
    
    with open('sendezentrum.csv', 'rb') as f:
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
        room = 'Saal 5'
        guid = hashlib.md5(room + event['Date'] + event['Time Start']).hexdigest()
        
        def norm(timestr):
            timestr = timestr.replace('p.m.', 'pm')
            timestr = timestr.replace('a.m.', 'am')
            ## workaround for failure in input file format
            if timestr.startswith('0:00'):
                timestr = timestr.replace('0:00', '12:00')
                
            return timestr
            
        
        start_time   = datetime.strptime( event['Date'] + ' ' + norm(event['Time Start']), date_format)
        if event['Time End'] != 'tbd':
            end_time = datetime.strptime( event['Date'] + ' ' + norm(event['Time End']  ), date_format)
        else:    
            end_time = start_time + timedelta(hours=2) 
        duration = (end_time - start_time).seconds/60
        
        # Chaos Communication Congress always starts at the 27th which is day 1
        # Maybe TODO: Use days[0]['start'] instead
        day = int(start_time.strftime('%d')) - 26
        
        event_n = OrderedDict([
            ('id', voc.tools.get_id(guid)),
            ('guid', guid),
            # ('logo', None),
            ('date', start_time.isoformat()),
            ('start', start_time.strftime('%H:%M')),
            #('duration', str(timedelta(minutes=event['Has duration'][0])) ),
            ('duration', '%d:%02d' % divmod(duration, 60) ),
            ('room', room),
            ('slug', ''),
            #('slug', '31c3_-_6561_-_en_-_saal_1_-_201412271100_-_31c3_opening_event_-_erdgeist_-_geraldine_de_bastion',
            ('title', event['Podcast'] + ': ' + event['Titel']),
            ('subtitle', ''),
            ('track', 'Sendezentrum'),
            ('type', 'Podcast'),
            ('language', 'de' ),
            ('abstract', ''),
            ('description', '' ),
            ('persons', [ OrderedDict([
                ('id', 0),
                ('full_public_name', p.strip()),
                #('#text', p),
            ]) for p in event['Teilnehmer'].split(',') ]),
            ('links', [])             
        ])
        
        #print event_n['title']
        
        day_rooms = schedule['schedule']['conference']['days'][day-1]['rooms']
        if room not in day_rooms:
            day_rooms[room] = list();
        day_rooms[room].append(event_n);
        
        
    
    #print json.dumps(schedule, indent=2)
    
    with open('sendezentrum.schedule.json', 'w') as fp:
        json.dump(schedule, fp, indent=4)
        
    with open('sendezentrum.schedule.xml', 'w') as fp:
        fp.write(voc.tools.dict_to_schedule_xml(schedule));
            
    print 'end'

if __name__ == '__main__':
    main()
