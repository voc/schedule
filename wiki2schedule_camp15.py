 # -*- coding: UTF-8 -*-

import requests
import json
from collections import OrderedDict
import dateutil.parser
from datetime import datetime
import pytz
import os
import sys

days = []
de_tz = pytz.timezone('Europe/Amsterdam')

# some functions used in multiple files of this collection
import voc.tools

wiki_url = 'https://events.ccc.de/camp/2015/wiki'
main_schedule_url = 'https://events.ccc.de/camp/2015/Fahrplan/schedule.json'
schedule2_url = 'https://frab.camp.berlin.ccc.de/en/ber15/public/schedule.json'
output_dir = "/srv/www/schedule/camp15"

if len(sys.argv) == 2:
    output_dir = sys.argv[1]

if not os.path.exists(output_dir):
    os.mkdir(output_dir) 
os.chdir(output_dir)


def process_wiki_events(events, sessions):
    global out, halfnarp_out, full_schedule, workshop_schedule
    
    for event_wiki_name, event_r in events.iteritems():
        print event_wiki_name
        event = event_r['printouts']
        temp = event_wiki_name.split('# ', 2);
        session_wiki_name = temp[0]
        guid = temp[1]
        
        if len(event['Has start time']) < 1:
            print "  has no start time"
            day_s = None
        else:
            start_time = de_tz.localize(datetime.fromtimestamp(int(event['Has start time'][0])))
            day_s = get_day(start_time)

        room = ''
        workshop_room_session = False
        # TODO can one Event take place in multiple rooms? 
        # WORKAROND If that is the case just pick the first one
        if len(event['Has session location']) == 1:
            #print event['Has session location']
            room = event['Has session location'][0]['fulltext'].split(':', 1)[1]
        
            workshop_room_session = (event['Has session location'][0]['fulltext'].split(':', 1)[0] == 'Room')
        elif len(event['Has session location']) == 0:
            print "  has no room yet"
        else:
            print "WARNING: has multiple rooms ???, just picking the first one…"
            event['Has session location'] = event['Has session location'][0]
        
        session = sessions[session_wiki_name]['printouts'];
        session['Has title'] = [session_wiki_name.split(':', 2)[1]]
        session['fullurl'] = sessions[session_wiki_name]['fullurl']
        
        # http://stackoverflow.com/questions/22698244/how-to-merge-two-json-string-in-python
        # This will only work if there are unique keys in each json string.
        combined = dict(session.items() + event.items())
        
        
        #print json.dumps(combined, indent=4)    
        
        out[event_wiki_name] = combined
        #if workshop_room_session and day_s is not None and event['Has duration']:
        if day_s is not None and event['Has duration']:
            '''
            if day_s not in schedule:
                schedule[day_s] = dict()
            if room not in schedule[day]:
                schedule[day_s][room] = list()
            schedule[day_s][room].append(combined)
            '''
            
            day = int(day_s)
            duration = 0
            if event['Has duration']:
                duration = event['Has duration'][0];
            lang = ''
            if session['Held in language']:
                lang = session['Held in language'][0].split(' - ', 1)[0]
            
            event_n = OrderedDict([
                ('id', voc.tools.get_id(guid)),
                ('guid', guid),
                ('logo', None),
                ('date', start_time.isoformat()),
                ('start', start_time.strftime('%H:%M')),
                #('duration', str(timedelta(minutes=event['Has duration'][0])) ),
                ('duration', '%d:%02d' % divmod(duration, 60) ),
                ('room', room),
                ('slug', ''),
                #('slug', '31c3_-_6561_-_en_-_saal_1_-_201412271100_-_31c3_opening_event_-_erdgeist_-_geraldine_de_bastion',
                ('title', session['Has title'][0]),
                ('subtitle', "\n".join(event['Has subtitle']) ),
                ('track', 'self organized sessions'),
                ('type', " ".join(session['Has session type']).lower()),
                ('language', lang ),
                ('abstract', ''),
                ('description', "\n".join(session['Has description'])),
                ('persons', [ OrderedDict([
                    ('id', 0),
                    ('full_public_name', p['fulltext'].split(':', 1)[1]),
                    ('url', p['fullurl']),
                ]) for p in session['Is organized by'] ]),
                ('links', session['Has website'] + [session['fullurl']])             
            ])
            
            wsdr = workshop_schedule["schedule"]["conference"]["days"][day]["rooms"]
            if room not in wsdr:
                wsdr[room] = list();
            wsdr[room].append(event_n);
            
            fsdr = full_schedule["schedule"]["conference"]["days"][day]["rooms"]
            if room not in fsdr:
                fsdr[room] = list();
            fsdr[room].append(event_n);
            
            halfnarp_out.append(OrderedDict([
                ("event_id", event_n['id']),
                ("track_id", 10),
                ("track_name", "Session"),
                ("room_id", 0),
                ("room_name", event_n['room']),
                ("start_time", event_n['date']),
                ("duration", duration*60),
                ("title", event_n['title']),
                ("abstract", event_n['abstract']),
                ("speakers", ", ".join([p['full_public_name'] for p in event_n['persons']])),
            ]))

def add_events_from_frab_schedule(other_schedule):
    
    for day in other_schedule["schedule"]["conference"]["days"]:
        if day["date"] != full_schedule["schedule"]["conference"]["days"][day["index"]]["date"]:
            print("the other schedule's days have to be the same like primary schedule")
            return False
        
        for room in day["rooms"]:
            full_schedule["schedule"]["conference"]["days"][day["index"]]["rooms"][room] = day["rooms"][room]
        
    
    return

def main():
    global wiki_url
    
    print "Requesting sessions"
    sessions_r = requests.get(
        wiki_url + '/index.php?title=Special:Ask', 
        params=(
            ('q', '[[Category:Session]]'),
            ('po', "\r\n".join([
                '?Has description',
                '?Has session type', 
                '?Held in language', 
                '?Is organized by', 
                '?Has website'])
            ),
            ('p[format]', 'json'),
            ('p[limit]', 500),
        ),
        verify=False #'cacert.pem'
    )
    print sessions_r.text
    
    print "Requesting events"
    events_r = requests.get(
        wiki_url + '/index.php?title=Special:Ask', 
        params=(
            ('q', '[[Has object type::Event]]'),
            ('po', "\r\n".join([
                '?Has subtitle',
                '?Has start time', '?Has end time', '?Has duration',
                '?Has session location', 
                '?Has event track',
                '?Has color'])
            ),
            ('p[format]', 'json'),
            ('p[limit]', 500),
        ),
        verify=False #'cacert.pem'
    )
    
    print "Requesting schedule"
    schedule_r = requests.get(
        main_schedule_url, 
        verify=False #'cacert.pem'
    )
    
    print "Requesting schedule from second frab" # , e.g. BER or Sendezentrum
    schedule2_r = requests.get(
        schedule2_url, 
        verify=False #'cacert.pem'
    )
    
    
    global full_schedule, workshop_schedule
        
    # this more complex way instead of sessions_r.json()['results'] is necessary 
    # to maintain the same order as in the input file
    sessions = json.JSONDecoder(object_pairs_hook=OrderedDict).decode(sessions_r.text)['results']
    events = json.JSONDecoder(object_pairs_hook=OrderedDict).decode(events_r.text)['results']
    full_schedule = json.JSONDecoder(object_pairs_hook=OrderedDict).decode(schedule_r.text)
    schedule2 = json.JSONDecoder(object_pairs_hook=OrderedDict).decode(schedule2_r.text)
    
    workshop_schedule = voc.tools.copy_base_structure(full_schedule, 5);
    
    # copy header for workshop schedule.xml/json from main frab schedule
    for day in workshop_schedule["schedule"]["conference"]["days"]:
        days.append({
            'index' : day['index'],
            'data' : day['date'],
            'start': dateutil.parser.parse(day['day_start']),
            'end': dateutil.parser.parse(day['day_end']),
        })
    
    #print json.dumps(workshop_schedule, indent=2)
    #print json.dumps(days, indent=2);
    
    print "Processing" 
    
    global out, halfnarp_out 
    out = {}
    halfnarp_out = []

    # add frab events from schedule2 to full_schedule
    add_events_from_frab_schedule(schedule2)
    
    # fill full_schedule, out and halfnarp_out
    process_wiki_events(events, sessions)
    

    #print json.dumps(workshop_schedule, indent=2)
    
    with open("sessions_complete.json", "w") as fp:
        json.dump(out, fp, indent=4)
    

    with open("workshops.schedule.json", "w") as fp:
        json.dump(workshop_schedule, fp, indent=4)
    
    with open('workshops.schedule.xml', 'w') as fp:
        fp.write(voc.tools.dict_to_schedule_xml(workshop_schedule))
    
    with open("workshops.halfnarp.json", "w") as fp:
        json.dump(halfnarp_out, fp, indent=4)
    
        
    with open("everything.schedule.json", "w") as fp:
        json.dump(full_schedule, fp, indent=4)
    
    with open('everything.schedule.xml', 'w') as fp:
        fp.write(voc.tools.dict_to_schedule_xml(full_schedule))   

    
    print 'end'


if os.path.isfile("_sos_ids.json"):
    with open("_sos_ids.json", "r") as fp:
        #sos_ids = json.load(fp) 
        # maintain order from file
        temp = fp.read()
        sos_ids = json.JSONDecoder(object_pairs_hook=OrderedDict).decode(temp)
    
    next_id = max(sos_ids.itervalues())+1

def get_day(start_time):
    for day in days:
        if day['start'] > start_time < day['end']:
            return day['index']
    
    return '0'

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
    
#os.system("git add *.json *.xml")
#os.system("git commit -m 'updates from " + str(datetime.now()) +  "'")
