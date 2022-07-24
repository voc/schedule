 # -*- coding: UTF-8 -*-

import requests
import json
from collections import OrderedDict
import dateutil.parser
from datetime import datetime
import pytz
import os
import sys
import traceback

reload(sys)
sys.setdefaultencoding('utf-8')


days = []
de_tz = pytz.timezone('Europe/Amsterdam')
local = False

# some functions used in multiple files of this collection
import voc.tools


wiki_url = 'https://events.ccc.de/congress/2015/wiki'
main_schedule_url = 'https://events.ccc.de/congress/2015/Fahrplan/schedule.json'
schedule2_url = 'https://frab.das-sendezentrum.de/de/32c3/public/schedule.json'
output_dir = "/srv/www/schedule/32C3"
secondary_output_dir = "./32C3"


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
    ('Hall 1', 359),
    ('Hall 2', 360),
    ('Hall G', 361),
    ('Hall 6', 362),    
    ('B\u00fchne', 1050),
    # ('Podcaster Tisch', 1051),
    ('Hall A.1', 1111),
    ('Hall A.2', 1112),
    ('Hall B',   1120),
    ('Hall C.1', 1131),
    ('Hall C.2', 1132),
    ('Hall C.3', 1133),
    ('Hall C.4', 1134),
    ('Hall F',   1230),
    ('Hall 13',  1013),
    ('Hall 14',  1014),
    ('Lounge',   1090),
    # TODO: Anti Error Lounge
])

def get_room_id(room_name):

    if room_name in room_map:
        return room_map[room_name]
    else:
        return 0;

track_map = {
  # cat talks_32c3.json | jq -c '.[] | [.track_name, .track_id]' | sort | uniq 
  "Art & Culture": 291,
  "CCC": 300,
  "Ethics, Society & Politics": 294,
  "Failosophy": 299,
  "Hardware & Making": 295,
  "Science": 297,
  "Security": 298,
}

def get_track_id(track_name):
    if track_name in track_map:
        return track_map[track_name]
    else:
        return 10;


def remove_prefix(foo):
    if ':' in foo:
        return foo.split(':', 1)[1]
    else:
        return foo

def process_wiki_events(events, sessions):
    global out, halfnarp_out, full_schedule, workshop_schedule
    
    for event_wiki_name, event_r in events.iteritems():
        print event_wiki_name
        try:
            event = event_r['printouts']
            temp = event_wiki_name.split('# ', 2);
            session_wiki_name = temp[0]
            guid = temp[1]
            
            if len(event['Has start time']) < 1:
                print "  has no start time"
                day_s = None
            else:
                time_stamp = event['Has start time'][0]
                date_time = datetime.fromtimestamp(int(time_stamp))
                start_time = de_tz.localize(date_time)
                day_s = get_day(start_time)
    
            room = ''
            workshop_room_session = False
            # TODO can one Event take place in multiple rooms? 
            # WORKAROND If that is the case just pick the first one
            if len(event['Has session location']) == 1:
                #print event['Has session location']
                room = remove_prefix(event['Has session location'][0]['fulltext'])
            
                workshop_room_session = (event['Has session location'][0]['fulltext'].split(':', 1)[0] == 'Room')
            elif len(event['Has session location']) == 0:
                print "  has no room yet"
            else:
                print "WARNING: has multiple rooms ???, just picking the first one…"
                event['Has session location'] = event['Has session location'][0]
            
            try:
                wiki_session = sessions[session_wiki_name]
            except KeyError as error:
                continue
            
            # print ""
            # print json.dumps(sessions, indent=4)
            # print ""
            # print json.dumps(wiki_session, indent=4)
            session = wiki_session['printouts'];
            try:
                # TODO: use remove_prefix()?
                session['Has title'] = [session_wiki_name.split(':', 2)[1]]
            except IndexError, e:
                print "Skipping malformed session wiki name {0}.".format(session_wiki_name)
                continue
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
                if session['Held in language'] and len(session['Held in language']) > 0:
                    lang = session['Held in language'][0]['fulltext'].split(' - ', 1)[0]
                
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
                    ('title', session['Has title'][0]),
                    ('subtitle', "\n".join(event['Has subtitle']) ),
                    ('track', 'self organized sessions'),
                    ('type', " ".join(session['Has session type']).lower()),
                    ('language', lang ),
                    ('abstract', ''),
                    ('description', "\n".join(session['Has description'])),
                    ('persons', [ OrderedDict([
                        ('id', 0),
                        ('url', p['fullurl']),
                        ('public_name', remove_prefix(p['fulltext'])), # must be last element so that transformation to xml works 
                    ]) for p in session['Is organized by'] ]),
                    ('links', session['Has website'] + [session['fullurl']])             
                ])
    
                # Break if conference day date and event date do not match
                conference_day_start = dateutil.parser.parse(workshop_schedule["schedule"]["conference"]["days"][day]["day_start"])
                conference_day_end = dateutil.parser.parse(workshop_schedule["schedule"]["conference"]["days"][day]["day_end"])
                event_n_date = dateutil.parser.parse(event_n.get('date'))
                if not conference_day_start <= event_n_date < conference_day_end:
                    raise Exception("Current conference day from {0} to {1} does not match current event {2} with date {3}."
                        .format(conference_day_start, conference_day_end, event_n["id"], event_n_date))
                
                fsdr = full_schedule["schedule"]["conference"]["days"][day]["rooms"]
                if room not in fsdr:
                    fsdr[room] = list();
                fsdr[room].append(event_n);
    
                
                if workshop_room_session:
                    wsdr = workshop_schedule["schedule"]["conference"]["days"][day]["rooms"]
                    if room not in wsdr:
                        wsdr[room] = list()
                    wsdr[room].append(event_n)
                
                    halfnarp_out.append(OrderedDict([
                        ("event_id", event_n['id']),
                        ("track_id", 10),
                        ("track_name", "Session"),
                        ("room_id", get_room_id(event_n['room'])),
                        ("room_name", event_n['room']),
                        ("start_time", event_n['date']),
                        ("duration", duration*60),
                        ("title", event_n['title']),
                        ("abstract", event_n['description']),
                        ("speakers", ", ".join([p['public_name'] for p in event_n['persons']])),
                    ]))
                
        except:
            print("  unexpected error: " + str(sys.exc_info()[0]))
            traceback.print_exc()
            print(json.dumps(event, indent=4))
            

def add_events_from_frab_schedule(other_schedule):
    
    for day in other_schedule["schedule"]["conference"]["days"]:
        if day["date"] != full_schedule["schedule"]["conference"]["days"][day["index"]]["date"]:
            print("the other schedule's days have to be the same like primary schedule")
            return False
        
        for room in day["rooms"]:
            full_schedule["schedule"]["conference"]["days"][day["index"]]["rooms"][room] = day["rooms"][room]
        
    
    return

def schedule_to_halfnarp(schedule):
    out = []
    for day in schedule["schedule"]["conference"]["days"]:
        for room in day['rooms']:
            for event_n in day['rooms'][room]:
                room_id = get_room_id(event_n['room'])
                
                if room_id != 0:
                    
                    track_id = get_track_id(event_n['track'])
                    track_name = event_n['track']
                    
                    duration = event_n['duration'].split(':')
                    if len(duration) > 2:
                        raise "  duration with three colons!?"
                    
                    text = ""
                    # if event_n['abstract']: 
                    #     text += event_n['abstract']
                    
                    if event_n['title'] == 'Lounge':
                        track_name = 'Session'
                        event_n['title'] = event_n['subtitle']
                        event_n['persons'] = []
                        text += event_n['description']
                    
                    elif track_name == 'self organized sessions':
                        track_name = 'Session'
                        text += event_n['subtitle'] + " \n"
                        text += event_n['description'][:200]
                    #if event_n['subtitle']:
                    #    title += " - " + event_n['subtitle']
                    
                    
                    out.append(OrderedDict([
                        ("event_id", event_n['id']),
                        ("track_id", track_id),
                        ("track_name", track_name),
                        ("room_id", room_id),
                        ("room_name", event_n['room']),
                        ("start_time", event_n['date']),
                        ("duration", int(duration[0])*3600+int(duration[1])*60),
                        ("title", event_n['title']),
                        ("abstract", text),
                        ("speakers", ", ".join([p['public_name'] for p in event_n['persons']])),
                    ]))
    return out
def wiki_request(q, po):
    r = None
    
    # Retry up to three times
    for _ in range(3):
        r = requests.get(
            wiki_url + '/index.php?title=Special:Ask', 
            params=(
                ('q', q),
                ('po', "\r\n".join(po)
                ),
                ('p[format]', 'json'),
                ('p[limit]', 500),
            ),
            verify=False #'cacert.pem'
        )
        if r.ok is True:
            break
        print(".")
        
    
    if r.ok is False:
        raise Exception("   Requesting failed, HTTP {0}.".format(r.status_code))
    return r

def main():
    global wiki_url
    
    print("Requesting wiki sessions")
    sessions_r = wiki_request('[[Category:Session]]', [
        '?Has description',
        '?Has session type', 
        '?Held in language', 
        '?Is organized by', 
        '?Has website'
    ])
    
    print("Requesting wiki events")
    events_r = wiki_request('[[Has object type::Event]]', [
        '?Has subtitle',
        '?Has start time', '?Has end time', '?Has duration',
        '?Has session location', 
        '?Has event track',
        '?Has color'
    ])

    print("Requesting main schedule")
    schedule_r = requests.get(
        main_schedule_url, 
        verify=False #'cacert.pem'
    )
    
    if schedule_r.ok is False:
        raise Exception("  Requesting main schedule failed, HTTP {0}.".format(schedule_r.status_code))

    print("Requesting schedule from second frab") # , e.g. BER or Sendezentrum
    schedule2_r = requests.get(
        schedule2_url, 
        verify=False #'cacert.pem'
    )
    
    if schedule2_r.ok is False:
        raise Exception("  Requesting schedule from second frab failed, HTTP {0}.".format(schedule2_r.status_code))


    print("Processing...")

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
    
    print "Combining data..." 
    
    global out, halfnarp_out 
    out = {}
    halfnarp_out = []

    # add frab events from schedule2 to full_schedule
    add_events_from_frab_schedule(schedule2)
    
    # add rooms now, to they are in the correct order
    for day in full_schedule["schedule"]["conference"]["days"]:
        for key in room_map.keys():
            if key not in day['rooms']:
                day['rooms'][key] = list()
    
    
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

    # TODO only main + second + workshops + lounge
    with open('common.halfnarp.json', 'w') as fp:
        json.dump(schedule_to_halfnarp(full_schedule), fp, indent=4)
        

    
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
