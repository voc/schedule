#!/usr/bin/env python
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
import optparse

# some functions used in multiple files of this collection
import voc.tools

# reconfigure default encoding to utf8 for python2
if sys.version_info.major < 3:
    reload(sys)
    sys.setdefaultencoding('utf-8')

#TODO for python3: 
# * fix NameError: name 'basestring' is not defined in voc.tools.dict_to_schedule_xml()

tz = pytz.timezone('Europe/Amsterdam')
time_stamp_offset = -3600 #  Workaround until MediaWiki server will be fixed

parser = optparse.OptionParser()
parser.add_option('--online', action="store_true", dest="online", default=False)
parser.add_option('--show-assembly-warnings', action="store_true", dest="show_assembly_warnings", default=False)
#parser.add_option('--fail', action="store_true", dest="exit_when_exception_occours", default=False)

options, args = parser.parse_args()
local = False
use_offline_frab_schedules = False
only_workshops = False


wiki_url = 'https://events.ccc.de/congress/2016/wiki'
main_schedule_url = 'https://fahrplan.events.ccc.de/congress/2016/Fahrplan/schedule.json' 
schedule2_url = 'https://frab.das-sendezentrum.de/de/33c3/public/schedule.json' 
output_dir = "/srv/www/33C3"
secondary_output_dir = "./33C3"


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
    #TODO   
    (u'Sendezentrumsbühne', 1050),
    ('Podcastingtisch', 1051),
    ('Hall A.1', 1111),
    ('Hall A.2', 1112),
    ('Hall B',   1120),
    ('Hall C.1', 1131),
    ('Hall C.2', 1132),
    ('Hall C.3', 1133),
    ('Hall C.4', 1134),
    ('Hall F',   1230),
    ('Hall 13-14',  1013),
    #('Hall 14',  1014),
    ('Lounge DisKo',   1090),
    # TODO: Lounge Section9
])


wsh_tpl = {
  "schedule": {
    "version": "XXX", 
    "conference": OrderedDict([
      ("acronym", "33c3"), 
      ("title", "33. Chaos Communication Congress"), 
      ("start", "2016-12-27"), 
      ("end", "2016-12-30"), 
      ("daysCount", 5), 
      ("timeslot_duration", "00:15"), 
      ("days", [
        {
          "index": 0, 
          "date": "2016-12-26", 
          "day_start": "2016-12-26T06:00:00+01:00", 
          "day_end": "2016-12-27T04:00:00+01:00", 
          "rooms": {}
        }, 
        {
          "index": 1, 
          "date": "2016-12-27", 
          "day_start": "2016-12-27T06:00:00+01:00", 
          "day_end": "2016-12-28T04:00:00+01:00", 
          "rooms": {}
        }, 
        {
          "index": 2, 
          "date": "2016-12-28", 
          "day_start": "2016-12-28T06:00:00+01:00", 
          "day_end": "2016-12-29T04:00:00+01:00", 
          "rooms": {}
        }, 
        {
          "index": 3, 
          "date": "2016-12-29", 
          "day_start": "2016-12-29T06:00:00+01:00", 
          "day_end": "2016-12-30T04:00:00+01:00", 
          "rooms": {}
        }, 
        {
          "index": 4, 
          "date": "2016-12-30", 
          "day_start": "2016-12-30T06:00:00+01:00", 
          "day_end": "2016-12-30T23:00:00+01:00", 
          "rooms": {}
        } 
      ])
    ]) 
  }
}


def get_room_id(room_name):

    if room_name in room_map:
        return room_map[room_name]
    else:
        return 0;

#TODO update for 33C3 or get halfnarp json form frab instead converting schedule.xml
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


warnings = False
events_with_warnings = 0
events_in_halls_with_warnings = 0
def process_wiki_events(events, sessions):
    global out, halfnarp_out, full_schedule, workshop_schedule, warnings
    events_total = 0
    events_successful = 0
    events_in_halls = 0 # aka workshops

    def warn(msg):
        global warnings, events_with_warnings, events_in_halls_with_warnings
        if not warnings:
            warnings = True
            events_with_warnings += 1
            if is_workshop_room_session:
                events_in_halls_with_warnings += 1
            
            if is_workshop_room_session or options.show_assembly_warnings:
                print('')
                print(event_wiki_name)
                if room: print('  at ' + room )
                print('  ' + wiki_edit_url)
            
        #if not is_workshop_room_session:
        #    msg += ' – at assembly?'
        if is_workshop_room_session or options.show_assembly_warnings:
            print(msg)
        
    # copy days meta data for usage by validation check in get_day()
    days = []
    for day in workshop_schedule["schedule"]["conference"]["days"]:
        days.append({
            'index' : day['index'],
            'date' : day['date'],
            'start': dateutil.parser.parse(day['day_start']),
            'end': dateutil.parser.parse(day['day_end']),
        })   
    #print(json.dumps(workshop_schedule, indent=2))
    #print(json.dumps(days, indent=2))
    
    def get_day(start_time):
        for day in days:
            if day['start'] <= start_time < day['end']:
                # print "Day {0}: day.start {1} <= start_time {2} < day.end {3}".format(day['index'], day['start'], start_time, day['end'])
                # print "Day {0}: day.start {1} <= start_time {2} < day.end {3}".format(day['index'], day['start'].strftime("%s"), start_time.strftime("%s"), day['end'].strftime("%s"))
                return day['index']
        
        warn("  illegal start time: " + start_time.isoformat())   
        return None

    def remove_prefix(foo):
        if ':' in foo:
            return foo.split(':', 1)[1]
        else:
            return foo
    
    for event_wiki_name, event_r in events.iteritems(): #python2
    #for event_wiki_name, event_r in events.items(): #pyhton3
        wiki_page_name = event_wiki_name.split('#')[0].replace(' ', '_') # or see fullurl property
        wiki_edit_url = wiki_url + '/index.php?title=' + wiki_page_name + '&action=edit'
        
        warnings = False
        
        #print(event_wiki_name + ' ' + wiki_edit_url)
        sys.stdout.write('.')
        
        try:
            event = event_r['printouts']
            temp = event_wiki_name.split('# ', 2);
            session_wiki_name = temp[0]
            guid = temp[1]
            room = ''
            is_workshop_room_session = False
            
            if session_wiki_name in sessions:
                wiki_session = sessions[session_wiki_name]
            else: 
                #is_workshop_room_session = True # workaround/don't ask 
                # This happens for imported events like these at the bottom of [[Static:Schedule]]
                warn('  event without session? -> ignore event')
                continue
        
            events_total += 1
                    
            # TODO can one Event take place in multiple rooms? – yes...
            # WORKAROND If that is the case just pick the first one
            if len(event['Has session location']) == 1:
                room = event['Has session location'][0]['fulltext']
                
                if room.split(':', 1)[0] == 'Room':
                    is_workshop_room_session = True
                    room = remove_prefix(room)
            
            elif len(event['Has session location']) == 0:
                warn("  has no room yet")
            else:
                warn("  WARNING: has multiple rooms ???, just picking the first one…")
                event['Has session location'] = event['Has session location'][0]
            
            
            
            if len(event['Has start time']) < 1:
                warn("  has no start time")
                day_s = None
            else:
                time_stamp = event['Has start time'][0]
                date_time = datetime.fromtimestamp(int(time_stamp) + time_stamp_offset)
                start_time = tz.localize(date_time)
                day_s = get_day(start_time)
    
            
            # print ""
            # print json.dumps(sessions, indent=4)
            # print ""
            # print json.dumps(wiki_session, indent=4)
            session = wiki_session['printouts'];
            try:
                # TODO: use remove_prefix()?
                session['Has title'] = [session_wiki_name.split(':', 2)[1]]
            except IndexError as e:
                warn("  Skipping malformed session wiki name {0}.".format(session_wiki_name))
                continue
            session['fullurl'] = sessions[session_wiki_name]['fullurl']
            
            # http://stackoverflow.com/questions/22698244/how-to-merge-two-json-string-in-python
            # This will only work if there are unique keys in each json string.
            combined = dict(session.items() + event.items()) #python2
            #combined = session.copy() #ptyhon3 TOOD test if this really leads to the same result
            #combined.update(event)
            
            
            #print json.dumps(combined, indent=4)    
            
            out[event_wiki_name] = combined
            #if is_workshop_room_session and day_s is not None and event['Has duration']:
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
                    ('title', session['Has title'][0]),
                    ('subtitle', "\n".join(event['Has subtitle']) ),
                    ('track', 'self organized sessions'),
                    ('type', " ".join(session['Has session type']).lower()),
                    ('language', lang ),
                    ('abstract', ''),
                    ('description', ("\n".join(session['Has description'])).strip()),
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
                
                # Events from day 0 (26. December) do not go into the full schdedule
                if day != 0 and not only_workshops:      
                    fsdr = full_schedule["schedule"]["conference"]["days"][day-1]["rooms"]
                    if room not in fsdr:
                        fsdr[room] = list();
                    fsdr[room].append(event_n);
    
                
                if is_workshop_room_session:
                    events_in_halls +=1
                    
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
                
                events_successful += 1
        except:
            print("  unexpected error: " + str(sys.exc_info()[0]))
            traceback.print_exc()
            print(json.dumps(event_n, indent=4))
            print(json.dumps(event, indent=4))
            
    
    print("\nFrom %d total events (%d in halls) where %d successful, while %d (%d in halls) produced warnings" % (events_total, events_in_halls, events_successful, events_with_warnings, events_in_halls_with_warnings))
    if not options.show_assembly_warnings:
        print(" (use --show-assembly-warnings cli option to show all warnings)")   

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


def parse_json(text):
    # this more complex way is necessary 
    # to maintain the same order as in the input file
    return json.JSONDecoder(object_pairs_hook=OrderedDict).decode(text)

def wiki_request(q, po):
    r = None
    
    print("Requesting wiki " + q)
    
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
            )
        )
        if r.ok is True:
            break
        print(".")
        
    
    if r.ok is False:
        raise Exception("   Requesting failed, HTTP {0}.".format(r.status_code))
    
    # this more complex way instead of sessions_r.json()['results'] is necessary 
    # to maintain the same order as in the input file
    results = parse_json(r.text)['results'] 
    
    return results

def json_request(url):
    print("Requesting " + url)
    schedule_r = requests.get(url) #, verify=False)
    
    if schedule_r.ok is False:
        raise Exception("  Request failed, HTTP {0}.".format(schedule_r.status_code))

    print("Requesting schedule frab") 
    schedule2_r = requests.get(
        schedule2_url, 
        verify=True #'cacert.pem'
    )
    schedule = parse_json(schedule_r.text)
    
    return schedule


def main():
    global full_schedule, workshop_schedule
        
    sessions = wiki_request('[[Category:Session]]', [
        '?Has description',
        '?Has session type', 
        '?Held in language', 
        '?Is organized by', 
        '?Has website'
    ])

    events = wiki_request('[[Has object type::Event]]', [
        '?Has subtitle',
        '?Has start time', '?Has end time', '?Has duration',
        '?Has session location', 
        '?Has event track',
        '?Has color'
    ])   
    
    if use_offline_frab_schedules:
        # python3: , encoding='utf-8'
        with open("schedule_main_rooms.json", "r") as fp:
            main_schedule = parse_json(fp.read())
        with open("schedule_sendezentrum.json", "r") as fp:    
            schedule2 = parse_json(fp.read()) 
        
    else:
        main_schedule = json_request(main_schedule_url)
        schedule2 = json_request(schedule2_url)

    print("Processing...")

    workshop_schedule = wsh_tpl# voc.tools.copy_base_structure(main_schedule, 5);
    

    print("Combining data...") 
    
    global out, halfnarp_out 
    out = {}
    halfnarp_out = []


    if not only_workshops:
        full_schedule = main_schedule.copy()

        # add frab events from schedule2 to full_schedule
        add_events_from_frab_schedule(schedule2)
    
        # add rooms now, so they are in the correct order
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
    
    if not only_workshops:    
        with open("everything.schedule.json", "w") as fp:
            json.dump(full_schedule, fp, indent=4)
        
        with open('everything.schedule.xml', 'w') as fp:
            fp.write(voc.tools.dict_to_schedule_xml(full_schedule))   
    
        # TODO only main + second + workshops + lounge
        with open('common.halfnarp.json', 'w') as fp:
            json.dump(schedule_to_halfnarp(full_schedule), fp, indent=4)
            

    
    print('done')


if os.path.isfile("_sos_ids.json"):
    with open("_sos_ids.json", "r") as fp:
        #sos_ids = json.load(fp) 
        # maintain order from file
        temp = fp.read()
        sos_ids = json.JSONDecoder(object_pairs_hook=OrderedDict).decode(temp)
    
    if sys.version_info.major < 3:
        next_id = max(sos_ids.itervalues())+1
    else:
        next_id = max(sos_ids.values())+1


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
