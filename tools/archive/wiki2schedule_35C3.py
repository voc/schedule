#!/usr/bin/env python2
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
from voc.schedule import Schedule

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
parser.add_option('--git', action="store_true", dest="git", default=False)


options, args = parser.parse_args()
local = False
use_offline_frab_schedules = False
only_workshops = False


congress_nr = 35
year = str(1983 + congress_nr)
xc3 = "{x}C3".format(x=congress_nr)

wiki_url = 'https://events.ccc.de/congress/{year}/wiki'.format(year=year)
main_schedule_url = 'http://fahrplan.events.ccc.de/congress/{year}/Fahrplan/schedule.json'.format(year=year)
additional_schedule_urls = [
    { 'name': 'chaos-west',     'url': 'https://fahrplan.chaos-west.de/35c3chaoswest/schedule/export/schedule.json',    'id_offset': 100},
    { 'name': 'chaoszone',      'url': 'https://cfp.chaoszone.cz/35c3/schedule/export/schedule.json',                   'id_offset': 700, 'options': { 
      'room-map': {
          'ChaosZone Stage @ 35c3': 'ChaosZone'
      }}
    },
    { 'name': 'sendezentrum',   'url': 'https://35c3.studio-link.de/35c3/schedule/export/schedule.json',                'id_offset': 400, 'options': { 
      'room-map': {
          u'Bühne': 'CCL Saal 3'
      }}
    },
    { 'name': 'wikipaka',       'url': 'https://cfp.verschwoerhaus.de/35c3/schedule/export/schedule.json',              'id_offset': 500},
    { 'name': 'lounges',        'url': 'https://fahrplan.events.ccc.de/congress/2018/Lineup/schedule.json',             'id_offset': None},
    { 'name': 'komona',         'url': 'https://talks.komona.org/35c3/schedule/export/schedule.json',                   'id_offset': 800},
    { 'name': 'open-infra',     'url': 'https://pretalx.35c3oio.freifunk.space/35c3oio/schedule/export/schedule.json',  'id_offset': 200},
#    { 'name': 'lightning',      'url': 'https://c3lt.de/35c3/schedule/export/schedule.json',                            'id_offset': 3000}
]


# this list/map is required to sort the events in the schedule.xml in the correct way
# other rooms/assemblies are added at the end on demand.
rooms = [
    "Lecture room 11",
    "Seminar room 14-15",
    "Seminar room 13",
    "Lecture room M1",
    "Lecture room M2",
    "Lecture room M3",
    "Kidspace",
    "CCL Saal 3",
    u"Chaos West Bühne",
    "ChaosZone",
    "OIO Vortrags-Arena",
    "OIO Workshop-Domo",
 
]

output_dir = "/srv/www/" + xc3
secondary_output_dir = "./" + xc3
#validator = sys.path[0] + "/validator/xsd/validate_schedule_xml.sh"
validator = "xmllint --noout --schema {path}/validator/xsd/schedule-without-person.xml.xsd".format(path=sys.path[0])

if len(sys.argv) == 2:
    output_dir = sys.argv[1]

if not os.path.exists(output_dir):
    try:
        if not os.path.exists(secondary_output_dir):
            os.mkdir(output_dir) 
        else:
            output_dir = secondary_output_dir
            local = True
    except:
        print('Please create directory named {} if you want to run in local mode'.format(secondary_output_dir))
        exit(-1)
os.chdir(output_dir)


wsh_tpl = {
  "schedule": OrderedDict([
    ("version", datetime.now().strftime('%Y-%m-%d %H:%M')),
    ("conference", OrderedDict([
      ("acronym", u"{}C3-workshops".format(congress_nr) ),
      ("title", u"{}. Chaos Communication Congress - Workshops".format(congress_nr)),
      ("start", year+"-12-26"),
      ("end", year+"-12-30"),
      ("daysCount", 5), 
      ("timeslot_duration", "00:15"), 
      ("days", [
        {
          "index": 0, 
          "date": year+"-12-26",
          "day_start": year+"-12-26T06:00:00+01:00",
          "day_end": year+"-12-27T04:00:00+01:00",
          "rooms": {}
        }, 
        {
          "index": 1, 
          "date": year+"-12-27",
          "day_start": year+"-12-27T06:00:00+01:00",
          "day_end": year+"-12-28T04:00:00+01:00",
          "rooms": {}
        }, 
        {
          "index": 2, 
          "date": year+"-12-28",
          "day_start": year+"-12-28T06:00:00+01:00",
          "day_end": year+"-12-29T04:00:00+01:00",
          "rooms": {}
        }, 
        {
          "index": 3, 
          "date": year+"-12-29",
          "day_start": year+"-12-29T06:00:00+01:00",
          "day_end": year+"-12-30T04:00:00+01:00",
          "rooms": {}
        }, 
        {
          "index": 4, 
          "date": year+"-12-30",
          "day_start": year+"-12-30T06:00:00+01:00",
          "day_end": year+"-12-30T23:00:00+01:00",
          "rooms": {}
        } 
      ])
    ])) 
  ])
}
warnings = False
events_with_warnings = 0
events_in_halls_with_warnings = 0

def process_wiki_events(events, sessions):
    global out, full_schedule, workshop_schedule, warnings
    events_total = 0
    events_successful = 0
    events_in_halls = 0 # aka workshops
    used_guids = []

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
    #for event_wiki_name, event_r in events.items(): #python3
        wiki_page_name = event_wiki_name.split('#')[0].replace(' ', '_') # or see fullurl property
        wiki_edit_url = wiki_url + '/index.php?title=' + wiki_page_name + '&action=edit'
        
        warnings = False
        
        #print(event_wiki_name + ' ' + wiki_edit_url)
        sys.stdout.write('.')
        
        try:
            event = event_r['printouts']
            temp = event_wiki_name.split('# ', 2)
            session_wiki_name = temp[0]

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
                time_stamp = event['Has start time'][0]['timestamp']
                date_time = datetime.fromtimestamp(int(time_stamp) + time_stamp_offset)
                start_time = tz.localize(date_time)
                day_s = get_day(start_time)
    
            
            # print ""
            # print json.dumps(sessions, indent=4)
            # print ""
            # print json.dumps(wiki_session, indent=4)
            session = wiki_session['printouts']
            try:
                session['Has title'] = [remove_prefix(session_wiki_name)]
            except IndexError as e:
                warn("  Skipping malformed session wiki name {0}.".format(session_wiki_name))
                continue
            session['fullurl'] = sessions[session_wiki_name]['fullurl']
            
            # http://stackoverflow.com/questions/22698244/how-to-merge-two-json-string-in-python
            # This will only work if there are unique keys in each json string.
            combined = dict(session.items() + event.items()) #python2
            #combined = session.copy() #python3 TOOD test if this really leads to the same result
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
                    duration = event['Has duration'][0]
                lang = ''
                if session['Held in language'] and len(session['Held in language']) > 0:
                    lang = session['Held in language'][0].split(' - ', 1)[0]

                if len(event['GUID']) > 0:
                    guid = event['GUID'][0]
                else:
                    guid = voc.tools.gen_uuid(session['fullurl'] + str(event['Has start time'][0]))
                    warn('   GUID was empty, generated one for now. Not shure if its stable...')
                
                if guid in used_guids:
                    warn('   GUID {} was already used before, generated a random one for now. Please fix the session wiki page to ensure users can stay subscribed to event!'.format(guid))
                    guid = voc.tools.gen_uuid(session['fullurl'] + str(event['Has start time'][0]))
                used_guids.append(guid)
                
                local_id = voc.tools.get_id(guid)
                #if id in used_ids:
                #    warn('   ID {} was already used before. Please fix the offsets to ensure users can stay subscribed to a event!'.format(guid))
                #used_ids.append(local_id)
                
                event_n = OrderedDict([
                    ('id', local_id),
                    ('guid', guid),
                    ('logo', None),
                    ('date', start_time.isoformat()),
                    ('start', start_time.strftime('%H:%M')),
                    #('duration', str(timedelta(minutes=event['Has duration'][0])) ),
                    ('duration', '%d:%02d' % divmod(duration, 60) ),
                    ('room', room),
                    # TODO use xc3.lower()
                    ('slug', '35c3-{id}-{name}'.format(id=local_id, name=voc.tools.normalise_string(session_wiki_name.lower()))),
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
                        fsdr[room] = list()
                    fsdr[room].append(event_n)
    
                
                if is_workshop_room_session:
                    events_in_halls +=1
                    
                    wsdr = workshop_schedule["schedule"]["conference"]["days"][day]["rooms"]
                    if room not in wsdr:
                        wsdr[room] = list()
                    wsdr[room].append(event_n)
                
                events_successful += 1
        except:
            print("  unexpected error: " + str(sys.exc_info()[0]))
            traceback.print_exc()
            print(json.dumps(event_n, indent=4))
            print(json.dumps(event, indent=4))
            
    
    print("\nFrom %d total events (%d in halls) where %d successful, while %d (%d in halls) produced warnings" % (events_total, events_in_halls, events_successful, events_with_warnings, events_in_halls_with_warnings))
    if not options.show_assembly_warnings:
        print(" (use --show-assembly-warnings cli option to show all warnings)")   

def add_events_from_frab_schedule(other_schedule, id_offset = None, options = None):

    primary_start = dateutil.parser.parse(full_schedule["schedule"]["conference"]["start"])
    other_start = dateutil.parser.parse(other_schedule["schedule"]["conference"]["start"])
    offset = (other_start - primary_start).days

    '''   try:
        while other_schedule["schedule"]["conference"]["days"][offset]["date"] != full_schedule["schedule"]["conference"]["days"][0]["date"]:
            offset += 1
    except:
        print("  ERROR: no overlap between other schedule and primary schedule")
        return False  '''

    for day in other_schedule["schedule"]["conference"]["days"]:
        target_day = day["index"] - 1 + offset 

        if target_day < 0:
            print( "  ignoring day {} from {}, as primary schedule starts at {}".format(
                day["date"], other_schedule["schedule"]["conference"]["acronym"], full_schedule["schedule"]["conference"]["start"]) 
            )
            continue

        if day["date"] != full_schedule["schedule"]["conference"]["days"][target_day]["date"]:
            print(target_day)
            print("  WARNING: the other schedule's days have to match primary schedule, in some extend!")
            return False
    
        for room in day["rooms"]:
            target_room = room
            if options and 'room-map' in options and room in options['room-map']:
                target_room = options['room-map'][room]

            if id_offset:
                for event in day["rooms"][room]:
                    event['id'] = int(event['id']) + id_offset
                    event['room'] = target_room
                # TODO? offset for person IDs?

            full_schedule["schedule"]["conference"]["days"][target_day]["rooms"][target_room] = day["rooms"][room]
        
    
    return True

def get_schedule(name, url):
    if use_offline_frab_schedules:
        # python3: , encoding='utf-8'
        with open("schedule_{}.json".format(name), "r") as fp:
            return parse_json(fp.read())
    else:
        return json_request(url)


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

    schedule = parse_json(schedule_r.text)
    
    return schedule

def export_schedule(filename, schedule):
    with open("{}.schedule.json".format(filename), "w") as fp:
        json.dump(schedule, fp, indent=4)
    
    with open('{}.schedule.xml'.format(filename), 'w') as fp:
        fp.write(Schedule(json=schedule).xml())

    # validate xml
    os.system('{} {}.schedule.xml'.format(validator, filename))





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
        '?Has color',
        '?GUID'
    ])   


    main_schedule = get_schedule('main_rooms', main_schedule_url)
    print("Processing...")

    workshop_schedule = wsh_tpl# voc.tools.copy_base_structure(main_schedule, 5)

    # add rooms now, so they are in the correct order
    for day in workshop_schedule["schedule"]["conference"]["days"]:
        for key in rooms:
            if key not in day['rooms']:
                day['rooms'][key] = list()
    
    
    print("Combining data...")

    if not only_workshops:
        full_schedule = main_schedule.copy()

        # add rooms now, so they are in the correct order
        for day in full_schedule["schedule"]["conference"]["days"]:
            for key in rooms:
                if key not in day['rooms']:
                    day['rooms'][key] = list()

        # add frab events from additional_schedule's to full_schedule
        for entry in additional_schedule_urls:
            try:
                other_schedule = get_schedule(entry['name'], entry['url'])
                
                if add_events_from_frab_schedule(other_schedule, id_offset=entry.get('id_offset'), options=entry.get('options')):
                    print("  success")
                if 'version' in other_schedule["schedule"]:
                    full_schedule["schedule"]["version"] += " " + other_schedule["schedule"]["version"]
                else:
                    print('  WARNING: schedule "{}" does not have a version number'.format(entry['name']))

            except:
                print("  UNEXPECTED ERROR:" + str(sys.exc_info()[1]))

    # write all imported schedules in to one merged schedule.json/xml
    export_schedule("import-merged", full_schedule)

    full_schedule["schedule"]["version"] += " " + workshop_schedule["schedule"]["version"]


    global out
    out = OrderedDict()
    # fill full_schedule and out
    process_wiki_events(events, sessions)
    

    #print json.dumps(workshop_schedule, indent=2)

    # write imported data from wiki to one merged file   
    with open("sessions_complete.json", "w") as fp:
        json.dump(out, fp, indent=4)

    # write all sessions in workshop rooms to an additional schedule.json/xml
    export_schedule("workshops", workshop_schedule)

    # write all events to one big schedule.json/xml
    if not only_workshops:    
        export_schedule("everything", full_schedule)
    
    print('files generation done')


if os.path.isfile("_sos_ids.json"):
    with open("_sos_ids.json", "r") as fp:
        # maintain order from file
        temp = fp.read()
        voc.tools.sos_ids = json.JSONDecoder(object_pairs_hook=OrderedDict).decode(temp)
    
    if sys.version_info.major < 3:
        voc.tools.next_id = max(voc.tools.sos_ids.itervalues())+1
    else:
        voc.tools.next_id = max(voc.tools.sos_ids.values())+1


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

if not local or options.git:      
    content_did_not_change = os.system('/usr/bin/env git diff -U0 --no-prefix | grep -e "^[+-]  " | grep -v version > /dev/null')

    def git(args):
        os.system('/usr/bin/env git {}'.format(args))

    if content_did_not_change:
        print('nothing relevant changed, reverting to previous state')
        git('reset --hard')
    else:
        git('add *.json *.xml')
        git('commit -m "version {} with {} new self-organized session(s)"'.format(full_schedule["schedule"]["version"], voc.tools.generated_ids))
        git('push')
