import sys
import os
import re
import json
import copy
import requests
import pytz
import dateutil.parser
from collections import OrderedDict
from typing import Callable, Dict, List, Union
from datetime import datetime, timedelta
from urllib.parse import urlparse
from lxml import etree as ET

try:
    import voc.tools as tools
    from voc.event import Event, EventSourceInterface
    from voc.room import Room
    from voc.logger import Logger
except ImportError:
    import tools
    from event import Event, EventSourceInterface
    from room import Room
    from logger import Logger


log = Logger(__name__)

# validator = f"{sys.path[0]}/validator/xsd/validate_schedule_xml.sh"
validator = f"xmllint --noout --schema {sys.path[0]}/validator/xsd/schedule.xml.xsd"
# validator = f"xmllint --noout --schema {sys.path[0]}/validator/xsd/schedule-without-person.xml.xsd"
validator_filter = ""


def set_validator_filter(filter):
    global validator_filter
    validator_filter += " | awk '" + " && ".join(["!/" + x + "/" for x in filter]) + "'"


class ScheduleException(Exception):
    pass


class ScheduleDay(dict):
    start: datetime = None
    end: datetime = None

    def __init__(
        self, i=None, year=None, month=12, day=None, tz=None, dt=None, json=None
    ):
        if i is not None and dt:
            self.start = dt
            self.end = dt + timedelta(hours=23)  # conference day lasts 23 hours

            dict.__init__(self, {
                "index": i + 1,
                "date": dt.strftime("%Y-%m-%d"),
                "day_start": self.start.isoformat(),
                "day_end": self.start.isoformat(),
                "rooms": {},
            })
            return
        elif json:
            dict.__init__(self, json)
        elif i is not None and (day or (year and day)):
            dict.__init__(self, {
                "index": i + 1,
                "date": "{}-{:02d}-{:02d}".format(year, month, day),
                "day_start": datetime(year, month, day, 6, 00, tzinfo=tz).isoformat(),
                "day_end": datetime(year, month, day + 1, 6, 00, tzinfo=tz).isoformat(),
                "rooms": {},
            })
        else:
            raise Exception("Either give JSON xor i, year, month, day")

        self.start = dateutil.parser.parse(self["day_start"])
        self.end = dateutil.parser.parse(self["day_end"])

    def json(self):
        return self


class Schedule(dict):
    """Schedule class with import and export methods"""
    _tz = None
    _days: list[ScheduleDay] = []
    _room_ids = {}
    origin_url = None
    origin_system = None
    stats = None
    generator = None

    def __init__(self, name: str = None, json=None, version: str = None, conference=None, start_hour=9):
        if json:
            dict.__init__(self, json["schedule"])
        elif conference:
            dict.__init__(self, {
                "version": version,
                "conference": conference
            })

        if "days" in self["conference"]:
            self._generate_stats("start" not in self["conference"])

        if "start" not in self["conference"]:
            self["conference"]["start"] = self.stats.first_event.start.isoformat()
        if "end" not in self["conference"]:
            self["conference"]["end"] = self.stats.last_event.end.isoformat()

        if "rooms" not in self["conference"]:
            # looks like we have an old style schedule json,
            # so let's construct room map from the scheduling data
            room_names = {}
            for day in self["conference"].get("days", []):
                # TODO: why are don't we use a Set?
                room_names.update([(k, None) for k in day["rooms"].keys()])
            self["conference"]["rooms"] = [{"name": name} for name in room_names]

        if "days" not in self["conference"] or len(self["conference"]["days"]) == 0:
            tz = self.tz()
            date = tz.localize(self.conference_start()).replace(hour=start_hour)
            days = []
            for i in range(self.conference("daysCount")):
                days.append(ScheduleDay(i, dt=date))
                date += timedelta(hours=24)
            self["conference"]["days"] = days

    @classmethod
    def from_url(cls, url, timeout=10):
        log.info("Requesting " + url)
        schedule_r = requests.get(url, timeout=timeout)

        if schedule_r.ok is False:
            schedule_r.raise_for_status()
            raise Exception(
                "  Request failed, HTTP {0}.".format(schedule_r.status_code)
            )

        data = schedule_r.json()

        # add sourounding schedule obj for inproperly formated schedule.json's
        if "schedule" not in data and "conference" in data:
            data = {"schedule": data}
        # move days into conference obj for inproperly formated schedule.json's
        if "days" in data['schedule']:
            data['schedule']['conference']['days'] = data['schedule'].pop("days")
            print(json.dumps(data, indent=2))

        if "version" not in data["schedule"]:
            data["schedule"]["version"] = ""

        schedule = Schedule(json=data)
        schedule.origin_url = url
        schedule.origin_system = urlparse(url).netloc
        return schedule

    @classmethod
    def from_file(cls, name):
        with open(name, "r") as fp:
            schedule = tools.parse_json(fp.read())
        return Schedule(json=schedule)

    @classmethod
    def from_template(
        cls, title, acronym, year, month, day, days_count=1, tz="Europe/Amsterdam"
    ):
        schedule = Schedule(
            version=datetime.now().strftime("%Y:%m-%d %H:%M"),
            conference={
                "acronym": acronym.lower(),
                "title": title,
                "start": "{}-{:02d}-{:02d}".format(year, month, day),
                "end": "{}-{:02d}-{:02d}".format(year, month, day + days_count - 1),
                "daysCount": days_count,
                "timeslot_duration": "00:15",
                "time_zone_name": tz,
            },
        )
        tzinfo = pytz.timezone(tz)
        days = schedule["conference"]["days"]
        for i in range(days_count):
            d = ScheduleDay(i, year, month, day + i, tz=tzinfo)
            days.append(d)

        return schedule

    @classmethod
    def from_dict(cls, template, start_hour=9):
        schedule = Schedule(json=template)

        return schedule

    @classmethod
    def from_XC3_template(cls, name, congress_nr, start_day, days_count):
        year = str(1983 + congress_nr)

        schedule = Schedule(
            version=datetime.now().strftime("%Y-%m-%d %H:%M"),
            conference={
                "acronym": f"{congress_nr}C3" + ("-" + name.lower() if name else ""),
                "title": f"{congress_nr}. Chaos Communication Congress" + (" - " + name if name else ""),
                "start": "{}-12-{}".format(year, start_day),
                "end": "{}-12-{}".format(year, start_day + days_count - 1),
                "daysCount": days_count,
                "timeslot_duration": "00:15",
                "time_zone_name": "Europe/Amsterdam",
            },
        )

        return schedule

    @classmethod
    def empty_copy_of(cls, parent_schedule: 'Schedule', name: str, start_hour=None):
        schedule = Schedule(
            version=datetime.now().strftime("%Y:%m-%d %H:%M"),
            conference=copy.deepcopy(parent_schedule.conference()),
        )
        schedule["conference"]["title"] += " - " + name

        for day in schedule["conference"]["days"]:
            if start_hour is not None:
                start = dateutil.parser.parse(day["day_start"]).replace(hour=start_hour)
                day["day_start"] = start.isoformat()
            day["rooms"] = []

        return schedule

    def reset_generator(self):
        self.generator = tools.generator_info()

    # TODO: test if this method still works after refactoring of Schedule class to dict child
    def copy(self, name=None):
        schedule = copy.deepcopy(self)
        if name:
            schedule["conference"]["title"] += f" - {name}"
        return Schedule(json={"schedule": schedule})

    def version(self):
        return self["version"]

    def tz(self):
        if not self._tz:
            self._tz = pytz.timezone(self.conference("time_zone_name"))
        return self._tz

    def conference(self, key=None, filter: Callable = None, fallback=None):
        if key:
            if filter:
                return next((item for item in self["conference"][key] if filter(item)), fallback)

            return self["conference"].get(key, fallback)
        else:
            return self["conference"]

    def conference_start(self):
        return dateutil.parser.parse(self.conference("start").split("T")[0])

    def days(self):
        # TODO return _days object list instead of raw dict/json?
        return self["conference"]["days"]

    def day(self, day: int):
        return self.days()[day - 1]

    def room(self, name=None, guid=None):
        if guid:
            return self.conference('rooms', lambda x: x['guid'] == guid, {'name': name, 'guid': guid})
        if name:
            return self.conference('rooms', lambda x: x['name'] == name, {'name': name, 'guid': guid})

        raise Exception('Either name or guid has to be provided')

    def rooms(self, mode='names'):
        if mode == 'names':
            return [room['name'] for room in self.conference('rooms')]
        elif mode == 'obj':
            return [Room.from_dict(r) for r in self.conference('rooms')]
        else:
            return self.conference('rooms')

    def add_rooms(self, rooms: list, context: EventSourceInterface = {}):
        if rooms:
            for x in rooms:
                self.add_room(x, context)

    def rename_rooms(self, replacements: Dict[str, str|Room]):

        name_replacements = {}

        for old_name_or_guid, new_room in replacements.items():
            new_name = new_room if isinstance(new_room, str) else new_room.name

            r = self.room(name=old_name_or_guid) or self.room(guid=old_name_or_guid)
            if r['name'] != new_name:
                name_replacements[r['name']] = new_name
                r['name'] = new_name
                if isinstance(new_room, Room) and new_room.guid:
                    r['guid'] = new_room.guid
                    self._room_ids[new_name] = new_room.guid
                elif r.get('guid'):
                    self._room_ids[new_name] = r['guid']

        for day in self['conference']['days']:
            for room_key, events in list(day['rooms'].items()):
                new_room = replacements.get(room_key, room_key)
                new_name = new_room if isinstance(new_room, str) else new_room.name

                day['rooms'][new_name] = day['rooms'].pop(room_key)
                if room_key != new_name:
                    for event in events:
                        event['room'] = new_name

    def add_room(self, room: Union[str, dict], context: EventSourceInterface = {}):
        # if rooms is str, use the old behaviour – for backwords compability
        if type(room) is str:
            for day in self.days():
                if room not in day["rooms"]:
                    day["rooms"][room] = list()
        # otherwise add new room dict to confernce
        elif "name" in room:
            if room["name"] in self._room_ids and self._room_ids[room["name"]] == room.get('guid'):
                # we know this room already, so return early
                return

            if 'location' in context:
                room['location'] = context['location']

            self.conference("rooms").append(room)
            self._room_ids[room["name"]] = room.get("guid")
            self.add_room(room["name"])

    def room_exists(self, day: int, name: str):
        return name in self.day(day)["rooms"]

    def add_room_on_day(self, day: int, name: str):
        self.day(day)["rooms"][name] = list()

    def add_room_with_events(self, day: int, target_room, data, origin=None):
        if not data or len(data) == 0:
            return

        #  log.debug('  adding room {} to day {} with {} events'.format(target_room, day, len(data)))
        target_day_rooms = self.day(day)["rooms"]

        if self.room_exists(day, target_room):
            target_day_rooms[target_room] += data
        else:
            target_day_rooms[target_room] = data


    # TODO this method should work woth both room key and room guid,
    #  but currently it only works with room name
    def remove_room(self, room_key: str):
        # if room key is a name, remove it directly from the room list
        if room_key in self._room_ids:
            del self._room_ids[room_key]

        obj = self.room(name=room_key)
        self["conference"]["rooms"].remove(obj)

        if room_key in self._room_ids:
            del self._room_ids[room_key]

        for day in self["conference"]["days"]:
            if room_key in day["rooms"]:
                del day["rooms"][room_key]

    def event(self, guid: str) -> Event:
        for day in self["conference"]["days"]:
            for room in day["rooms"]:
                for event in day["rooms"][room]:
                    if event['guid'] == guid:
                        if isinstance(event, Event):
                            return event
                        else:
                            return Event(event)

    def add_event(self, event: Event, options=None):
        day = self.get_day_from_time(event.start)
        if event.get("slug") is None:
            event["slug"] = "{acronym}-{id}-{name}".format(
                acronym=self.conference()["acronym"],
                id=event["id"],
                name=tools.normalise_string(event["title"]),
            )

        if not self.room_exists(day, event["room"]):
            self.add_room_on_day(day, event["room"])

        self.days()[day - 1]["rooms"][event["room"]].append(event)

    def foreach_event(self, func, *args):
        out = []
        for day in self["conference"]["days"]:
            for room in day["rooms"]:
                for event in day["rooms"][room]:
                    result = func(event if isinstance(event, Event) else Event(event), *args)
                    if result:
                        out.append(result)
        return out

    def foreach_event_raw(self, func, *args):
        out = []
        for day in self["conference"]["days"]:
            for room in day["rooms"]:
                for event in day["rooms"][room]:
                    result = func(event, *args)
                    if result:
                        out.append(result)

        return out

    def foreach_day_room(self, func):
        out = []
        for day in self["conference"]["days"]:
            for room in day["rooms"]:
                result = func(day["rooms"][room])
                if result:
                    out.append(result)

        return out

    def _generate_stats(self, enable_time_stats=False, verbose=False):
        class ScheduleStats:
            min_id = None
            max_id = None
            person_min_id = None
            person_max_id = None
            events_count = 0
            first_event: Event = None
            last_event: Event = None

        self.stats = ScheduleStats()

        def calc_stats(event: Event):
            self.stats.events_count += 1

            id = int(event["id"])
            if self.stats.min_id is None or id < self.stats.min_id:
                self.stats.min_id = id
            if self.stats.max_id is None or id > self.stats.max_id:
                self.stats.max_id = id

            if self.stats.first_event is None or event.start < self.stats.first_event.start:
                self.stats.first_event = event
            if self.stats.last_event is None or event.start < self.stats.last_event.start:
                self.stats.last_event = event

            for person in event.get("persons", []):
                if "id" in person and (isinstance(person["id"], int) or person["id"].isnumeric()):
                    if (
                        self.stats.person_min_id is None
                        or int(person["id"]) < self.stats.person_min_id
                    ):
                        self.stats.person_min_id = int(person["id"])
                    if (
                        self.stats.person_max_id is None
                        or int(person["id"]) > self.stats.person_max_id
                    ):
                        self.stats.person_max_id = int(person["id"])

        self.foreach_event(calc_stats)

        if verbose:
            print(f"  from {self['conference']['start']} to {self['conference']['end']}")
            print( "  contains {events_count} events, with local ids from {min_id} to {max_id}".format(**self.stats.__dict__))  # noqa
            print( "    local person ids from {person_min_id} to {person_max_id}".format(**self.stats.__dict__)) # noqa
            print(f"    rooms: {', '.join(self.rooms())}")


    def get_day_from_time(self, start_time):
        for i in range(self.conference("daysCount")):
            day = self.day(i + 1)
            if day.start <= start_time < day.end:
                # print(f"Day {day.index}: day.start {day.start} <= start_time {start_time} < day.end {day.end}")
                #print(f"Day {day['index']}: day.start {day['start'].strftime('%s')} <= start_time {start_time.strftime('%s')} < day.end {day['end'].strftime('%s')}")
                return day["index"]

        raise Warning("  illegal start time: " + start_time.isoformat())

    def add_events_from(self, other_schedule, id_offset=None, options={}, context: EventSourceInterface = {}):
        offset = (
            other_schedule.conference_start() - self.conference_start()
        ).days
        days = other_schedule.days()
        # worksround if other schedule starts with index 0 instead of 1
        if days[0]["index"] == 0:
            offset += 1

        self["version"] += " " + other_schedule.version()

        if offset:
            log.warning("  calculated conference start day index offset: {}".format(offset))

        for day in days:
            target_day = day["index"] + offset

            if target_day < 1:
                log.warning(f"  ignoring day {day['date']} from {other_schedule.conference('acronym')}, as primary schedule starts at {self.conference('start')}")
                continue

            if day["date"] != self.day(target_day)["date"]:
                log.error(f"  ERROR: the other schedule's days have to match primary schedule, in some extend {day['date']} != {self.day(target_day)['date']}!")
                return False

            self.add_rooms(other_schedule.conference("rooms"), context)

            for room in day["rooms"]:
                if options and "room-map" in options and room in options["room-map"]:
                    target_room = options["room-map"][room]

                    for event in day["rooms"][room]:
                        event["room"] = target_room
                elif options and "room-prefix" in options:
                    target_room = options["room-prefix"] + room
                else:
                    target_room = room

                events = []
                for event in day["rooms"][room]:
                    if options.get("track"):
                        event["track"] = options['track'](event) if callable(options["track"]) else options["track"]

                    if options.get("do_not_record"):
                        event["do_not_record"] = options['do_not_record'](event) if callable(options["do_not_record"]) else options["do_not_record"]

                    if options.get("remove_title_additions"):
                        # event["title"], subtitle, event_type = re.match(r"^(.{15,}?)(?:(?::| [–-]+) (.+?))?(?: \((.+?)\))?$", event["title"]).groups()

                        match = re.match(r"^(.{5,}?)(?:(?::| [–-]+) (.+?))?(?: \((.+?)\))?$", event["title"])
                        if match:
                            event["title"], subtitle, event_type = match.groups()

                        if not event.get("subtitle") and subtitle:
                            event["subtitle"] = subtitle

                    if options.get("rewrite_id_from_question"):
                        q = next(
                            (
                                x
                                for x in event["answers"]
                                if x.question == options["rewrite_id_from_question"]
                            ),
                            None,
                        )
                        if q is not None:
                            event["id"] = q["answer"]
                    elif id_offset:
                        event["id"] = int(event["id"]) + id_offset
                        # TODO? offset for person IDs?

                    # workaround for fresh pretalx instances
                    elif options.get("randomize_small_ids") and int(event["id"]) < 1500:
                        event["id"] = int(re.sub("[^0-9]+", "", event["guid"])[0:4])

                    # overwrite slug for pretalx schedule.json input
                    if options.get("overwrite_slug", False):
                        event["slug"] = "{slug}-{id}-{name}".format(
                            slug=self.conference("acronym").lower(),
                            id=event["id"],
                            name=tools.normalise_string(event["title"].split(":")[0]),
                        )

                    if options.get("prefix_person_ids"):
                        prefix = options.get("prefix_person_ids")
                        for person in event["persons"]:
                            person["id"] = f"{prefix}-{person['id']}"

                    events.append(event if isinstance(event, Event) else Event(event, origin=other_schedule))

                # copy whole day_room to target schedule
                self.add_room_with_events(target_day, target_room, events)
        return True

    def find_event(self, id=None, guid=None):
        if not id and not guid:
            raise RuntimeError("Please provide either id or guid")

        if id:
            result = self.foreach_event(
                lambda event: event if event["id"] == id else None
            )
        else:
            result = self.foreach_event(
                lambda event: event if event["guid"] == guid else None
            )

        if len(result) > 1:
            log.warning("Warning: Found multiple events with id " + id)
            return result

        if len(result) == 0:
            raise Warning("could not find event with id " + id)
            # return None

        return result[0]

    def remove_event(self, id=None, guid=None):
        if not id and not guid:
            raise RuntimeError("Please provide either id or guid")

        for day in self["conference"]["days"]:
            for room in day["rooms"]:
                for event in day["rooms"][room]:
                    if (
                        event["id"] == id
                        or event["id"] == str(id)
                        or event["guid"] == guid
                    ):
                        log.info("removing", event["title"])
                        day["rooms"][room].remove(event)

    # dict_to_etree from http://stackoverflow.com/a/10076823

    # TODO:
    #  * check links conversion
    #  * ' vs " in xml
    #  * logo is in json but not in xml
    # formerly named dict_to_schedule_xml()
    def xml(self, method="string"):
        root_node = None

        def dict_to_attrib(d, root):
            assert isinstance(d, dict)
            for k, v in d.items():
                assert _set_attrib(root, k, v)

        def _set_attrib(tag, k, v):
            if isinstance(v, str):
                tag.set(k, v)
            elif isinstance(v, int):
                tag.set(k, str(v))
            else:
                log.error("  error: unknown attribute type %s=%s" % (k, v))

        def _to_etree(d, node, parent=""):
            if not d:
                pass
            elif isinstance(d, str):
                node.text = d
            elif isinstance(d, int):
                node.text = str(d)
            elif parent == "person":
                node.text = d.get("public_name") or d.get('full_public_name') or d.get('full_name') or d.get('name')
                if "id" in d:
                    _set_attrib(node, "id", d["id"])
                if "guid" in d:
                    _set_attrib(node, "guid", d["guid"])

            elif (
                isinstance(d, dict)
                or isinstance(d, OrderedDict)
                or isinstance(d, Event)
                or isinstance(d, ScheduleDay)
            ):
                # location of base_url sadly differs in frab's json and xml serialization :-(
                if parent == "schedule" and "base_url" in d:
                    d["conference"]["base_url"] = d["base_url"]
                    del d["base_url"]

                # count variable is used to check how many items actually end as elements
                # (as they are mapped to an attribute)
                count = len(d)
                recording_license = ""
                for k, v in d.items():
                    if parent == "day":
                        if k[:4] == "day_":
                            # remove day_ prefix from items
                            k = k[4:]

                    if (
                        k == "id"
                        or k == "guid"
                        or (parent == "day" and isinstance(v, (str, int)))
                        or parent == "generator"
                        or parent == "track"
                        or parent == "color"
                    ):
                        _set_attrib(node, k, v)
                        count -= 1
                    elif k == "url" and parent in ["link", "attachment"]:
                        _set_attrib(node, "href", v)
                        count -= 1
                    elif k == "title" and parent in ["link", "attachment"]:
                        node.text = v
                    elif count == 1 and isinstance(v, str):
                        node.text = v
                    else:
                        node_ = node

                        if parent == "room":
                            # create room tag for each instance of a room name
                            node_ = ET.SubElement(node, "room")
                            node_.set("name", k or '')
                            if k in self._room_ids and self._room_ids[k]:
                                node_.set("guid", self._room_ids[k])

                            k = "event"

                        if k == "days":
                            # in the xml schedule days are not a child of a conference,
                            # but directly in the document node
                            node_ = root_node

                        # ignore room list on confernce
                        if k == 'rooms' and parent == 'conference':
                            continue
                        # special handing for collections: days, rooms etc.
                        elif k[-1:] == "s":
                            # don't ask me why the pentabarf schedule xml schema is so inconsistent --Andi
                            # create collection tag for specific tags, e.g. persons, links etc.
                            if parent == "event":
                                node_ = ET.SubElement(node, k)

                            # remove last char (which is an s)
                            k = k[:-1]
                        # different notation for conference length in days
                        elif parent == "conference" and k == "daysCount":
                            k = "days"
                        # special handling for recoding_licence and do_not_record flag
                        elif k == "recording_license":
                            # store value for next loop iteration
                            recording_license = v
                            # skip forward to next loop iteration
                            continue
                        elif k == "do_not_stream":
                            # we dont expose this flag to the schedule.xml, only in schedule.json
                            continue
                        elif k == "do_not_record" or k == "recording":
                            k = "recording"
                            # not in schedule.json: license information for an event
                            v = {
                                "license": recording_license,
                                "optout": v,
                            }
                        # new style schedule.json (version 2022-12)
                        elif k == "optout":
                            v = "true" if v is True else "false"

                        # iterate over lists
                        if isinstance(v, list):
                            for element in v:
                                _to_etree(element, ET.SubElement(node_, k), k)
                        # don't single empty room tag, as we have to create one for each room, see above
                        elif parent == "day" and k == "room":
                            _to_etree(v, node_, k)
                        else:
                            _to_etree(v, ET.SubElement(node_, k), k)
            else:
                assert d == "invalid type"

        assert isinstance(self, dict)

        root_node = ET.Element("schedule")
        root_node.set("{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation", "https://c3voc.de/schedule/schema.xsd")
        _to_etree(self, root_node, "schedule")

        if method == 'xml':
            return root_node
        elif method == 'bytes':
            return ET.tostring(root_node, pretty_print=True, xml_declaration=True)

        return ET.tostring(root_node, pretty_print=True, encoding="unicode", doctype='<?xml version="1.0"?>')

    def json(self, method="json", **args):
        json = {
            "$schema": "https://c3voc.de/schedule/schema.json",
            "schedule": {
                "generator": self.generator or tools.generator_info(),
                **self
            }
        }
        if method == 'string':
            return json.dumps(self, indent=2, cls=ScheduleEncoder, **args)

        return json

    def filter(self, name: str, rooms: Union[List[Union[str, Room]], Callable]):
        log.info(f'\nExporting {name}... ')
        schedule = self.copy(name)

        if callable(rooms):
            def filterRoom(room):
                return rooms(room)
        else:
            room_names = set()
            room_guids = set()
            for room in rooms:
                if isinstance(room, Room):
                    if room.guid:
                        room_guids.add(room.guid)
                    if room.name:
                        room_names.add(room.name)

            def filterRoom(room: Room):
                if isinstance(room, Room):
                    return room.name in room_names or \
                        room.guid in room_guids
                else:
                    return room['name'] in room_names or \
                        room.get('guid', '') in room_guids

        for room in schedule.rooms(mode='obj'):
            if not filterRoom(room):
                log.info(f"deleting room {room.name} on conference")
                schedule.remove_room(room.name)

        schedule['version'] = self.version().split(';')[0]
        return schedule

    def export(self, prefix):
        with open("{}.schedule.json".format(prefix), "w") as fp:
            json.dump(self.json(), fp, indent=2, cls=ScheduleEncoder)

        with open("{}.schedule.xml".format(prefix), "w") as fp:
            fp.write(self.xml())

        # TODO use python XML validator instead of shell call
        # validate xml
        result = os.system(
            f'/bin/bash -c "{validator} {prefix}.schedule.xml 2>&1 {validator_filter}; exit \\${{PIPESTATUS[0]}}"'
        )
        if result != 0 and validator_filter:
            log.warning("  (validation errors might be hidden by validator_filter)")

    def __str__(self):
        return json.dumps(self, indent=2, cls=ScheduleEncoder)


class ScheduleEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Schedule):
            return obj.json()
        if isinstance(obj, ScheduleDay):
            return obj
        if isinstance(obj, Event):
            return obj.json()
        return json.JSONEncoder.default(self, obj)
