import requests
import json
from collections import OrderedDict
import dateutil.parser
from datetime import datetime
import sys
import os
import copy
from lxml import etree as ET
#from xml.etree import cElementTree as ET


import voc.tools as tools


#workaround to be python 3 compatible
if sys.version_info[0] >= 3:
    basestring = str


#validator = '{path}/validator/xsd/validate_schedule_xml.sh'.format(path=sys.path[0])
validator = 'xmllint --noout --schema {path}/validator/xsd/schedule-without-person.xml.xsd'.format(path=sys.path[0])
validator_filter = ''

def set_validator_filter(filter):
    global validator_filter
    validator_filter += " | awk '" + (' && '.join(['!/'+x+'/' for x in filter]) + "'")
    

class Day:
    _day = None
    start = None
    end = None
    def __init__(self, i = None, year = None, month = 12, day = None, json = None):
        if json:
            self._day = json
        elif i and year and day:
           self._day = {
                "index": i+1, 
                "date": "{}-12-{}".format(year, day),
                "day_start": "{}-12-{}T06:00:00+01:00".format(year, day),
                "day_end": "{}-12-{}T04:00:00+01:00".format(year, day+1),
                "rooms": {}
            }
        else:
            raise Exception('Either give JSON xor i, year, month, day')
        
        self.start = dateutil.parser.parse(self._day["day_start"])
        self.end = dateutil.parser.parse(self._day["day_end"])
 
    def __getitem__(self, key):
        return self._day[key]


class Event:
    _event = None
    start = None

    def __init__(self, attributes, start_time = None):
        self._event = OrderedDict(attributes)
        self.start = start_time or dateutil.parser.parse(self._event['date'])

    def __getitem__(self, key):
        return self._event[key]

    def __len__(self):
        return len(self._event)
    
    def items(self):
        return self._event.items()

    def __str__(self):
        return json.dumps(self._event, indent=2)

    def export(self, prefix):
        with open("{}{}.json".format(prefix, self._event['guid']), "w") as fp:
            json.dump(self._event, fp, indent=2)


class Schedule:
    ''' 
    Schedule class with import and export methods 
    '''
    _schedule = None
    _days = []

    def __init__(self, name = None, url = None, json = None):
        # TODO remove or revert class methods below to object methods
        #if url:
        #    self.from_url(url)
        if json:
            self._schedule = json

        self._days = [None] * self.conference()['daysCount']

    @classmethod
    def from_url(cls, url):
        print("Requesting " + url)
        schedule_r = requests.get(url) #, verify=False)
        
        if schedule_r.ok is False:
            raise Exception("  Request failed, HTTP {0}.".format(schedule_r.status_code))

        #self.schedule = tools.parse_json(schedule_r.text) 

        # this more complex way is necessary 
        # to maintain the same order as in the input file
        schedule = json.JSONDecoder(object_pairs_hook=OrderedDict).decode(schedule_r.text) 

        return Schedule(json=schedule)

    @classmethod
    def from_file(cls, name):
        with open("schedule_{}.json".format(name), "r") as fp:
            schedule = tools.parse_json(fp.read())

        return Schedule(json=schedule)

    @classmethod
    def from_XC3_template(cls, name, congress_nr, start_day, days_count):
        year = str(1983 + congress_nr)
        
        schedule = {
            "schedule": OrderedDict([
                ("version", datetime.now().strftime('%Y-%m-%d %H:%M')),
                ("conference", OrderedDict([
                    ("acronym", u"{}C3-{}".format(congress_nr, name.lower()) ),
                    ("title", u"{}. Chaos Communication Congress - {}".format(congress_nr, name)),
                    ("start", "{}-12-{}".format(year, start_day)),
                    ("end", "{}-12-{}".format(year, start_day+days_count-1)),
                    ("daysCount", days_count), 
                    ("timeslot_duration", "00:15"), 
                    ("days", [])
                ])) 
            ])
        }
        days = schedule['schedule']['conference']['days']
        day = start_day 
        for i in range(days_count):
            days.append({
                "index": i+1, 
                "date": "{}-12-{}".format(year, day),
                "day_start": "{}-12-{}T06:00:00+01:00".format(year, day),
                "day_end": "{}-12-{}T04:00:00+01:00".format(year, day+1),
                "rooms": OrderedDict()
            })
            day += 1

        return Schedule(json=schedule)
    
    @classmethod
    def empty_copy_of(cls, parent_schedule, name):        
        schedule = {
            "schedule": OrderedDict([
                ("version", datetime.now().strftime('%Y-%m-%d %H:%M')),
                ("conference", copy.deepcopy(parent_schedule.conference())) 
            ])
        }
        schedule['schedule']['conference']['title'] += ' - ' + name
        for day in schedule['schedule']['conference']['days']:
            day['rooms'] = OrderedDict()
        return Schedule(json=schedule)

    def copy(self, name):        
        schedule = copy.deepcopy(self._schedule)
        schedule['schedule']['conference']['title'] += ' - ' + name
        return Schedule(json=schedule)

    def __getitem__(self, key):
        return self._schedule['schedule'][key]

    def schedule(self):
        return self._schedule['schedule']
    
    def version(self):
        return self._schedule['schedule']['version']

    def conference(self, key = None):
        if key:
            return self._schedule['schedule']['conference'][key]
        else: 
            return self._schedule['schedule']['conference']
    
    def days(self):
        # TODO return _days object list instead of raw dict/json?
        return self._schedule['schedule']['conference']['days']

    def day(self, day):
        if not self._days[day-1]:
            self._days[day-1] = Day(json=self.days()[day-1])

        return self._days[day-1]

    def add_rooms(self, rooms):
        for day in self._schedule['schedule']['conference']['days']:
            for key in rooms:
                if key not in day['rooms']:
                    day['rooms'][key] = list()

    def room_exists(self, day, room):
        return room in self.days()[day-1]['rooms']
    
    def add_room(self, day, room):
        self.days()[day-1]['rooms'][room] = list()

    def add_room_with_events(self, day, target_room, data):
        if not data or len(data) == 0:
            return
        
        #print('  adding room {} to day {} with {} events'.format(target_room, day, len(data)))
        target_day_rooms = self.days()[day-1]['rooms']

        if self.room_exists(day, target_room):
            target_day_rooms[target_room] += data
        else:
            target_day_rooms[target_room] = data

    def add_event(self, event):
        day = self.get_day_from_time(event.start)

        if not self.room_exists(day, event['room']):
            self.add_room(day, event['room'])
        
        self.days()[day-1]['rooms'][event['room']].append(event)


    def foreach_event(self, func):
        out = []
        for day in self._schedule['schedule']['conference']['days']:
            for room in day['rooms']:
                for event in day['rooms'][room]:
                    out.append(func(event))
        
        return out
    
    def get_day_from_time(self, start_time):
        for i in range(self.conference()['daysCount']):
            day = self.day(i+1)
            if day.start <= start_time < day.end:
                # print "Day {0}: day.start {1} <= start_time {2} < day.end {3}".format(day['index'], day['start'], start_time, day['end'])
                # print "Day {0}: day.start {1} <= start_time {2} < day.end {3}".format(day['index'], day['start'].strftime("%s"), start_time.strftime("%s"), day['end'].strftime("%s"))
                return day['index']
        
        raise Warning("  illegal start time: " + start_time.isoformat())   

    def export(self, prefix):
        with open("{}.schedule.json".format(prefix), "w") as fp:
            json.dump(self._schedule, fp, indent=2, cls=ScheduleEncoder)
    
        with open('{}.schedule.xml'.format(prefix), 'w') as fp:
            fp.write(self.xml())

        # validate xml
        result = os.system('{validator} {prefix}.schedule.xml 2>&1 {filter}'.format(validator=validator, prefix=prefix, filter=validator_filter) + '; exit ${PIPESTATUS[0]}')
        if result != 0 and validator_filter:
            print('  (some validation errors might be hidden by validator_filter)')

    def __str__(self):
        return json.dumps(self._schedule, indent=2, cls=ScheduleEncoder)

    def add_events_from(self, other_schedule, id_offset = None, options = None):
        primary_start = dateutil.parser.parse(self.conference()["start"])
        other_start = dateutil.parser.parse(other_schedule.conference()["start"])
        offset = (other_start - primary_start).days

        self._schedule['schedule']['version'] += " " + other_schedule.version()

        if offset:
            print ("  calculated conference start day offset: {}".format(offset))

        for day in other_schedule.days():
            target_day = day["index"] + offset

            if target_day < 1:
                print( "  ignoring day {} from {}, as primary schedule starts at {}".format(
                    day["date"], other_schedule.conference()["acronym"], self.conference()["start"]) 
                )
                continue

            if day["date"] != self.day(target_day)["date"]:
                #print(target_day)
                print("  ERROR: the other schedule's days have to match primary schedule, in some extend!")
                return False
        
            for room in day["rooms"]:
                target_room = room
                if options and 'room-map' in options and room in options['room-map']:
                    target_room = options['room-map'][room]
                    
                    for event in day["rooms"][room]:
                        event['room'] = target_room
                
                if id_offset:
                    for event in day["rooms"][room]:
                        event['id'] = int(event['id']) + id_offset
                    # TODO? offset for person IDs?

                # copy whole day_room to target schedule
                self.add_room_with_events(target_day, target_room, day["rooms"][room])
        
        
        return True



    # dict_to_etree from http://stackoverflow.com/a/10076823

    # TODO:
    #  * check links conversion
    #  * ' vs " in xml
    #  * logo is in json but not in xml

    def xml(self):
        root_node = None
                
        def dict_to_attrib(d, root):
            assert isinstance(d, dict)
            for k, v in d.items():
                assert _set_attrib(root, k, v)

        def _set_attrib(tag, k, v):
            if isinstance(v, basestring):
                tag.set(k, v)
            elif isinstance(v, int):
                tag.set(k, str(v))
            else:
                print("  error: unknown attribute type %s=%s" % (k, v))

        def _to_etree(d, node, parent = ''):
            if not d:
                pass
            elif isinstance(d, basestring):
                node.text = d
            elif isinstance(d, int):
                node.text = str(d)
            elif isinstance(d, dict) or isinstance(d, OrderedDict) or isinstance(d, Event):
                if parent == 'schedule' and 'base_url' in d:
                    d['conference']['base_url'] = d['base_url']
                    del d['base_url']

                # count variable is used to check how many items actually end as elements 
                # (as they are mapped to an attribute)
                count = len(d)
                recording_license = ''
                for k,v in d.items():
                    if parent == 'day':
                        if k[:4] == 'day_':
                            # remove day_ prefix from items
                            k = k[4:]
                    
                    if k == 'id' or k == 'guid' or (parent == 'day' and isinstance(v, (basestring, int))):
                        _set_attrib(node, k, v)
                        count -= 1
                    elif k == 'url' and parent != 'event':
                        _set_attrib(node, 'href', v)
                        count -= 1
                    elif count == 1 and isinstance(v, basestring):
                        node.text = v
                    else:
                        node_ = node

                        if parent == 'room':
                            # create room tag for each instance of a room name
                            node_ = ET.SubElement(node, 'room')
                            node_.set('name', k)
                            k = 'event'
                            
                        if k == 'days':
                            # in the xml schedule days are not a child of a conference, but directly in the document node
                            node_ = root_node     
                        
                        # special handing for collections: days, rooms etc.
                        if k[-1:] == 's':              
                            # don't ask me why the pentabarf schedule xml schema is so inconsistent --Andi 
                            # create collection tag for specific tags, e.g. persons, links etc.
                            if parent == 'event':
                                node_ = ET.SubElement(node, k)
                            
                            # remove last char (which is an s)
                            k = k[:-1] 
                        # different notation for conference length in days
                        elif parent == 'conference' and k == 'daysCount':
                            k = 'days'
                        # special handling for recoding_licence and do_not_record flag
                        elif k == 'recording_license':
                            # store value for next loop iteration 
                            recording_license = v
                            # skip forward to next loop iteration
                            continue       
                        elif k == 'do_not_record':
                            k = 'recording'
                            # not in schedule.json: license information for an event
                            v = OrderedDict([
                                ('license', recording_license), 
                                ('optout', 'true' if v else 'false')
                            ])

                        if isinstance(v, list):
                            for element in v:
                                _to_etree(element, ET.SubElement(node_, k), k)
                        # don't single empty room tag, as we have to create one for each room, see above
                        elif parent == 'day' and k == 'room':
                            _to_etree(v, node_, k)
                        else:
                            _to_etree(v, ET.SubElement(node_, k), k)
            else: assert d == 'invalid type'
        assert isinstance(self._schedule, dict) and len(self._schedule) == 1
        tag, body = next(iter(self._schedule.items()))

        root_node = ET.Element(tag)
        _to_etree(body, root_node, 'schedule')
        
        if sys.version_info[0] >= 3:
            return ET.tounicode(root_node, pretty_print = True)
        else:
            return ET.tostring(root_node, pretty_print = True, encoding='UTF-8')

class ScheduleEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Schedule): 
            return obj._schedule
        if isinstance(obj, Event): 
            return obj._event
        return json.JSONEncoder.default(self, obj)