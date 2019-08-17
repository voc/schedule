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
from voc.schedule import Schedule, Event

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
parser.add_option('--fail', action="store_true", dest="exit_when_exception_occours", default=False)
parser.add_option('--git', action="store_true", dest="git", default=False)
parser.add_option('--debug', action="store_true", dest="debug", default=False)


options, args = parser.parse_args()
local = False
use_offline_frab_schedules = False
only_workshops = False

if __name__ == '__main__':
    congress_nr = 35
    year = str(1983 + congress_nr)
    xc3 = "{x}C3".format(x=congress_nr)

    wiki_url = 'https://events.ccc.de/congress/{year}/wiki'.format(year=year)

    output_dir = "/srv/www/" + xc3
    secondary_output_dir = "./" + xc3

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

    if not os.path.exists("events"):
        os.mkdir("events")


    # this list/map is required to sort the events in the schedule.xml in the correct way
    # other rooms/assemblies are added at the end on demand.
    rooms = [
        "Lecture room 11",
        "Seminar room 14-15",
        "Seminar room 13",
        "Lecture room M1",
        "Lecture room M2",
        "Lecture room M3"
    ]

def print_json(x):
    try:
        print(json.dumps(x, indent=2))
    except:
        print('Fallback: ', x)

def generate_wiki_schedules(wiki_url):
    global wiki_schedule, workshop_schedule
    
    data = Wiki(wiki_url)

    print("Processing...")

    wiki_schedule = Schedule.from_XC3_template('Wiki', congress_nr, 27, 4)
    wiki_schedule.add_rooms(rooms)

    # workshops are all events from the wiki, which are in workshop rooms – starting from day 0 (the 26.)
    workshop_schedule = Schedule.from_XC3_template('Workshops', congress_nr, 26, 5)
    workshop_schedule.add_rooms(rooms)
    
    
    print("Combining data...")

    global sessions_complete
    sessions_complete = OrderedDict()

    # process_wiki_events() fills global variables: out, wiki_schedule, workshop_schedule
    process_wiki_events(data, wiki_schedule, workshop_schedule)
    
    # write imported data from wiki to one merged file   
    with open("sessions_complete.json", "w") as fp:
        json.dump(sessions_complete, fp, indent=2)

    wiki_schedule.export("wiki")
    # write all sessions in workshop rooms to an additional schedule.json/xml
    workshop_schedule.export("workshops")
    
    print('done')
    return wiki_schedule

warnings = False
events_with_warnings = 0
events_in_halls_with_warnings = 0


# this method is also exported to be used as a library method, thereby we started to reduce requiring of global variables
def process_wiki_events(wiki, wiki_schedule, workshop_schedule = None, timestamp_offset = None, options = None):
    global sessions_complete, warnings, time_stamp_offset

    if not timestamp_offset == None:
        time_stamp_offset = timestamp_offset

    sessions_complete = OrderedDict()
    events_total = 0
    events_successful = 0
    events_in_halls = 0 # aka workshops
    used_guids = []
    debug = options and options.debug

    def warn(msg, force = False):
        global warnings, events_with_warnings, events_in_halls_with_warnings
        if not warnings:
            warnings = True
            events_with_warnings += 1
            if is_workshop_room_session:
                events_in_halls_with_warnings += 1
            
            if is_workshop_room_session or options.show_assembly_warnings or force:
                print('')
                print(event_wiki_name)
                try: print('  at ' + start_time.isoformat() ) 
                except NameError: pass
                try: print('  in ' + room ) 
                except NameError: pass
                print('  ' + wiki_edit_url)
            
        #if not is_workshop_room_session:
        #    msg += ' – at assembly?'
        if is_workshop_room_session or options.show_assembly_warnings or force:
            print(msg)
    
    #for event_wiki_name, event_r in wiki.events.iteritems(): #python2
    for event_wiki_name, event_r in wiki.events.items(): #python3
        
        warnings = False
        sys.stdout.write('.')
        
        try:
            wiki_page_name = event_wiki_name.split('#')[0].replace(' ', '_') # or see fullurl property
            wiki_edit_url = wiki.wiki_url + '/index.php?title=' + wiki_page_name + '&action=edit'
            
            session = wiki.parent_of_event(event_wiki_name)
            event = event_r['printouts']
            event_n = None
            events_total += 1
                    
            # One Event take place in multiple rooms...
            # WORKAROND If that is the case just pick the first one
            room = ''
            is_workshop_room_session = False
            if len(event['Has session location']) == 1:
                room = event['Has session location'][0]['fulltext']
                
                if room.split(':', 1)[0] == 'Room':
                    is_workshop_room_session = True
                    room = Wiki.remove_prefix(room)
            
            elif len(event['Has session location']) == 0:
                warn("  has no room yet, skipping...")
                continue
            else:
                warn("  WARNING: has multiple rooms ???, just picking the first one…")
                event['Has session location'] = event['Has session location'][0]['fulltext']
            
            # http://stackoverflow.com/questions/22698244/how-to-merge-two-json-string-in-python
            # This will only work if there are unique keys in each json string.
            #combined = dict(session.items() + event.items()) #python2
            combined = session.copy() #python3 TOOD test if this really leads to the same result
            combined.update(event)
            sessions_complete[event_wiki_name] = combined         
            
            if len(event['Has start time']) < 1:
                warn("  has no start time")
                day = None
            else:
                date_time = datetime.fromtimestamp(int(event['Has start time'][0]['timestamp']) + time_stamp_offset)
                start_time = tz.localize(date_time)
                day = wiki_schedule.get_day_from_time(start_time)
    
            #if is_workshop_room_session and day is not None and event['Has duration']:
            if day is not None and event['Has duration']:                
                duration = 0
                if event['Has duration']:
                    duration = event['Has duration'][0]['value']

                if duration > 60*24:
                    warn('   event takes longer than 24h, skipping...')
                    continue


                lang = ''
                if session['Held in language'] and len(session['Held in language']) > 0:
                    lang = session['Held in language'][0].split(' - ', 1)[0]

                if len(event['GUID']) > 0:
                    guid = event['GUID'][0]
                    if not isinstance(guid, str):
                        raise Exception('GUID is not string, but ' + guid)
                else:
                    guid = voc.tools.gen_uuid(session['fullurl'] + str(event['Has start time'][0]))
                    warn('   GUID was empty, generated one for now. Not shure if its stable...')
                    #if debug:
                    #    print_json(event['GUID'])
                if guid in used_guids:
                    warn('   GUID {} was already used before, generated a random one for now. Please fix the session wiki page to ensure users can stay subscribed to event!'.format(guid), force=True)
                    guid = voc.tools.gen_uuid(session['fullurl'] + str(event['Has start time'][0]))
                used_guids.append(guid)

                local_id = voc.tools.get_id(guid)

                event_n = Event([
                    ('id', local_id),
                    ('guid', guid),
                    ('url', "https:"+session['fullurl']),
                    ('logo', None),
                    ('date', start_time.isoformat()),
                    ('start', start_time.strftime('%H:%M')),
                    #('duration', str(timedelta(minutes=event['Has duration'][0])) ),
                    ('duration', '%d:%02d' % divmod(duration, 60) ),
                    ('room', room),
                    ('slug', '{slug}-{id}-{name}'.format(
                        slug=wiki_schedule.conference()['acronym'].lower(),
                        id=local_id,
                        name=voc.tools.normalise_string(session['wiki_name'].lower())
                    )),
                    ('title', session['Has title'][0]),
                    ('subtitle', "\n".join(event['Has subtitle']) ),
                    ('track', 'self organized sessions'),
                    ('type', " ".join(session['Has session type']).lower()),
                    ('language', lang ),
                    ('abstract', ''),
                    ('description', ("\n".join(session['Has description'])).strip()),
                    ('persons', [ OrderedDict([
                        ('id', 0),
                        ('url', 'https:'+p['fullurl']),
                        ('public_name', Wiki.remove_prefix(p['fulltext'])), # must be last element so that transformation to xml works
                    ]) for p in session['Is organized by'] ]),
                    ('links', session['Has website'])
                ], start_time)
    
                # Break if conference day date and event date do not match
                conference_day_start = wiki_schedule.day(day).start
                conference_day_end = wiki_schedule.day(day).end
                if not conference_day_start <= event_n.start < conference_day_end:
                    raise Exception("Current conference day from {0} to {1} does not match current event {2} with date {3}."
                        .format(conference_day_start, conference_day_end, event_n["id"], event_n.start))
                
                # Events from day 0 (26. December) do not go into the full schdedule
                if start_time.day != 26 and not only_workshops:      
                    wiki_schedule.add_event(event_n)
                
                if workshop_schedule and is_workshop_room_session:
                    events_in_halls +=1
                    workshop_schedule.add_event(event_n)
                
                events_successful += 1
        except Warning as w:
            warn(w)
        except:
            if 'event_n' in locals(): print(event_n)
            if 'event' in locals(): print(json.dumps(event, indent=2))
            print("  unexpected error: " + str(sys.exc_info()[0]))
            traceback.print_exc()
            if options.exit_when_exception_occours: 
                exit()
            
    store_sos_ids()

    if debug:
        with open("sessions_complete.json", "w") as fp:
            json.dump(sessions_complete, fp, indent=2)

    print("\nFrom %d total events (%d in halls) where %d successful, while %d (%d in halls) produced warnings" % (events_total, events_in_halls, events_successful, events_with_warnings, events_in_halls_with_warnings))
    if not options.show_assembly_warnings:
        print(" (use --show-assembly-warnings cli option to show all warnings)") 
        


class Wiki:
    '''
    This class is a container for self-organized sessions from a Semantic Mediawiki instance.
    One session can have one or multiple events (aka slots) when it takes place.
    '''
    wiki_url = None
    sessions = []
    events = []

    def __init__(self, wiki_url):
        self.wiki_url = wiki_url
        self.sessions = self.query('[[Category:Session]]', [
            '?Has description',
            '?Has session type', 
            '?Held in language', 
            '?Is organized by', 
            '?Has website',
            '?Modification date'
        ])

        self.events = self.query('[[Has object type::Event]]', [
            '?Has subtitle',
            '?Has start time', '?Has end time', '?Has duration',
            '?Has session location', 
            '?Has event track',
            '?Has color',
            '?GUID'
        ])

    def query(self, q, po):
        r = None
        
        print("Requesting wiki " + q)
        
        # Retry up to three times
        for _ in range(3):
            r = requests.get(
                self.wiki_url + '/index.php?title=Special:Ask', 
                params=(
                    ('q', q),
                    ('po', "\r\n".join(po)),
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
        results = voc.tools.parse_json(r.text)['results'] 
        
        return results

    
    def parent_of_event(self, event_wiki_name):
        session_wiki_name = event_wiki_name.split('# ', 2)[0]

        if session_wiki_name in self.sessions:
            wiki_session = self.sessions[session_wiki_name]
        else: 
            #is_workshop_room_session = True # workaround/don't ask 
            # This happens for imported events like these at the bottom of [[Static:Schedule]]
            raise Warning('  event without session? -> ignore event')

        session = wiki_session['printouts']
        session['fullurl'] = wiki_session['fullurl']
        session['wiki_name'] = session_wiki_name

        try:
            session['Has title'] = [Wiki.remove_prefix(session_wiki_name)]
        except IndexError:
            raise Warning("  Skipping malformed session wiki name {0}.".format(session_wiki_name))

        return session

    
    @classmethod
    def remove_prefix(cls, foo):
        if ':' in foo:
            return foo.split(':', 1)[1]
        else:
            return foo



def load_sos_ids():
    if os.path.isfile("_sos_ids.json"):
        with open("_sos_ids.json", "r") as fp:
            # maintain order from file
            temp = fp.read()
            voc.tools.sos_ids = json.JSONDecoder(object_pairs_hook=OrderedDict).decode(temp)
        
        if sys.version_info.major < 3:
            voc.tools.next_id = max(voc.tools.sos_ids.itervalues())+1
        else:
            voc.tools.next_id = max(voc.tools.sos_ids.values())+1

def store_sos_ids():
    #write sos_ids to disk
    with open("_sos_ids.json", "w") as fp:
        json.dump(voc.tools.sos_ids, fp, indent=4)

load_sos_ids()

if __name__ == '__main__':
    generate_wiki_schedules(wiki_url)

    if not local or options.git:  
        os.system("/usr/bin/env git add *.json *.xml")
        os.system("/usr/bin/env git commit -m 'updates from " + str(datetime.now()) +  "'")
        #os.system("/usr/bin/env git push")
