import re
import icalendar
import requests

from voc import GenericConference
from voc.event import Event, EventSourceInterface
from voc.schedule import Schedule, ScheduleException
from voc.tools import format_duration, gen_person_uuid, gen_uuid


class WebcalConference2(GenericConference, EventSourceInterface):
    def __init__(self, **args):
        GenericConference.__init__(self, **args)

    def schedule(self, template: Schedule):
        if not self.schedule_url or self.schedule_url == 'TBD':
            raise ScheduleException('  has no schedule url yet – ignoring')

        url = re.sub(r'^webcal', 'http', self.schedule_url)
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            raise ScheduleException(f'  Failed to retrieve iCal feed: Error ({r.status_code})')
        cal = icalendar.Calendar.from_ical(r.text)

        schedule = template.copy(self['name']) or Schedule(conference=self)

        for e in cal.walk('vevent'):
            try:
                event = Event(convert_to_dict(e, self), origin=self)
                schedule.add_event(event)
            except Exception as e:
                print(e)

        return schedule


def convert_to_dict(e: icalendar.Event, context: WebcalConference2) -> dict:
    # title, subtitle, event_type = re.match(r"^(.+?)(?:( ?[:–] .+?))?(?: \((.+?)\))?$", e.name).groups()
    track, = [ str(c) for c in e.get('categories').cats]  or [None]
    begin = e['dtstart'].dt
    end = e['dtend'].dt
    duration = end - begin

    return { k: (v if isinstance(v, list) or v is None else str(v))  for k, v in {
        "guid": gen_uuid(e['uid']),
        "id": e['event-id'],
        "title": e.get('summary'),
        "subtitle": '',
        "abstract": e['description'],
        "description": '',  # empty description for pretalx importer (temporary workaround)
        "date": begin.isoformat(),
        "start": begin.strftime("%H:%M"),
        "duration": format_duration(duration),
        "room": track, #context['name'],
        "persons": [{
            **p,
            "id": 0
        } for p in extract_persons(e)],
        "track": track,
        "language": 'de',
        "type": 'Session' or 'Other',
        "url": e.get('url', None),
    }.items() }

def extract_persons(e: icalendar.Event) -> list:
    person_str = str(e.get('location', '')).replace(' und ', '; ').strip()
    print(person_str)
    # persons = re.split(r'\s*[,;/]\s*', person_str)
    persons = re.split(r'[,;/](?![^()]*\))', person_str)

    if len(persons) == 0:
        return []
    pattern = r'([^()]+)(?:\((\w{2,3}\s+)?([^)]*)\))'

    result = []
    for p in persons:
        # p is either "name (org)" or or "name (org role)" or "name (name@org.tld)"
        match = re.match(pattern, p)
        if match:
            name, org, role = match.groups()
            if role and '@' in role:
                match = re.search(r'@(.+)(\.de)?$', role)
                org = match.group(1)
                result.append({
                    "name": name.strip(),
                    "org": org.strip(),
                    "email": role.strip(),
                    "guid": gen_person_uuid(role)
                })
            else:
                if not org:
                    if len(role) <= 3:
                        org = role
                        role = None
                    else:
                        # try catch `Distribution Cordinator, ZER` and split org
                        m = re.match(r'^(.+?), (\w{2,3})$', role)
                        if m:
                            org = m.group(2)
                            role = m.group(1)

                if name:
                    result.append({
                        "name": name.strip(),
                        "org": org.strip() if org else None,
                        "role": role.strip() if role else None,
                    })
        elif p:
            result.append({
                "name": p.strip(),
            })

    print(result)
    print()
    return result


if __name__ == '__main__':
    WebcalConference()