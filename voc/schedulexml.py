from collections.abc import Callable, Generator
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import ElementTree
from datetime import datetime, timedelta 
import dateutil.parser

import requests

try:
    from voc.event import Event
except ImportError:
    from event import Event


# from https://git.cccv.de/hub/hub/-/blob/develop/src/core/schedules/schedulexml.py#L65

class ScheduleXML:
    """
    Schedule from XML document using etree, with inspirations from
      - https://github.com/pretalx/pretalx-downstream/blob/master/pretalx_downstream/tasks.py#L67
      - https://github.com/Zverik/schedule-convert/blob/master/schedule_convert/importers/frab_xml.py#L55
    """

    _schedule: ElementTree
    tz = None

    def __init__(self, etree):
        self._schedule = etree

    @classmethod
    def from_url(cls, url):
        r = requests.get(url)

        if r.ok is False:
            raise Exception(f'Request failed, HTTP {r.status_code}.')

        # TODO: with lxml we could use the remove_blank_text option to avoid whitespace-only text nodes
        #etree = ET.fromstring(r.text, parser=ET.XMLParser(encoding='utf-8', remove_blank_text=True))
        etree = ET.fromstring(r.text)

        # Close the raw file handle if it's still open
        if hasattr(r, 'raw') and r.raw.closed is False:
            r.raw.close()

        return ScheduleXML(etree=etree)

    @classmethod
    def from_file(cls, path):
        etree = ET.parse(path)
        return ScheduleXML(etree=etree)


    def __getitem__(self, key):
        return self._schedule.find(key)

    def schedule(self):
        return self._schedule

    def version(self):
        v = self._schedule.find('version')
        return v.text if v is not None else None
    
    def base_url(self):
        b = self._schedule.find('base_url') or self._schedule.find('conference/base_url')
        return b.text if b is not None else None

    def conference(self, key=None, filter: Callable|None = None, fallback=None):
        c = self._schedule.find('conference')
        assert c is not None, "Schedule XML must contain a conference node"

        if key:
            if filter:
                return next((item for item in c.find(key) if filter(item)), fallback)

            return c.find(key) or fallback if c is not None else fallback
        else:
            return c

    def days(self):
        return self._schedule.findall('day')

    def rooms(self):
        rooms = {}
        for day in self.days():
            for room in day.findall('room'):
                room_name = room.attrib['name']
                room_guid = room.attrib.get('guid')
                room_desc = room.attrib.get('description')
                rooms[room_name] = {'guid': room_guid, 'name': room_name, 'description': room_desc}

        return list(rooms.values())

    def events(self) -> Generator['EventXML', None, None]:
        for day in self.days():
            date = day.attrib.get('date')  # Get date from day element
            for room in day.findall('room'):
                for event in room.findall('event'):
                    e = EventXML(event, parent=self, day_date=date)
                    e['id'] = event.attrib.get('id')
                    e['guid'] = event.attrib.get('guid')
                    yield e

    # TODO: make this more efficient by: 
    #   a) filter before creating Event objects  and/or
    #   b) building an index of events by id and guid
    def event(self, id=None, guid=None):
        for event in self.events():
            if (id and event['id'] == id) or (guid and event['guid'] == guid):
                return event
        return None

    def foreach_event(self, func, *args):
        out = []
        for event in self.events():
            result = func(event, *args)
            if result:
                out.append(result)
        return out

    def __str__(self):
        return ET.tounicode(self._schedule, pretty_print=True)


class EventXML(Event[ElementTree]):
    def __init__(self, tree: ElementTree, parent: ScheduleXML, start_time=None, day_date=None):
        self._conference = parent
        self._event = tree
        self._values = {}
        if start_time:
            self.start: datetime = start_time
        else:
            # First try to find a 'date' node in the event
            node = self._event.find('date')
            
            if node is not None:
                self.start = dateutil.parser.parse(node.text)
            elif day_date:
                # If no 'date' on Event, combine day_date with event's start time
                start_node = self._event.find('start')
                if start_node is not None and start_node.text:
                    # Combine day date with event start time
                    combined = f"{day_date} {start_node.text}"
                    self.start = dateutil.parser.parse(combined)
                    # Store the combined date in _values for Event class
                    self._values['date'] = self.start.isoformat()
                else:
                    self.start = None
            else:
                self.start = None
        
        # Very old schedule.xml variants e.g. from Datenspuren 2008 have no slug, but tag. 
        # In that case, we can use the tag as slug
        if not self['slug'] and self['tag']:
            self._values['slug'] = self['tag']

    def persons(self) -> list[str]:
        persons = self._event.findall('persons/person')
        return [p.text or '' for p in persons]

    def url(self):
        url_node = self._event.find('url')
        if url_node is not None and url_node.text:
            return url_node.text
        
        if self['id'] and self._conference and self._conference.base_url():
            return self._conference.base_url().format(id=self['id'])

        return None

    def __getitem__(self, key):
        # First check if the value is _values, eg. id or guid from event attributes
        if key in self._values:
            return self._values[key]

        # TODO: map do_not_record to recording="false" in XML

        # Otherwise, try to find the value in the XML tree
        item = self._event.find(key)

        # cleanup whitespace from xml values, e.g. for description
        return "".join(item.itertext()).strip() if item is not None else None

    def __setitem__(self, key, value):
        self._values[key] = value

    def __iter__(self):
        # TODO
        return self._event.__iter__()

    def __len__(self):
        # TODO
        return len(self._event)

    def __lt__(self, other):
        return self.start < other.start

    def items(self):
        # TODO
        return self._event.items()
