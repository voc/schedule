import re
import ics
import requests

from voc import GenericConference
from voc.event import Event, EventSourceInterface
from voc.schedule import Schedule, ScheduleException
from voc.tools import format_duration, gen_person_uuid


class WebcalConference(GenericConference, EventSourceInterface):
    def __init__(self, **args):
        GenericConference.__init__(self, **args)

    def schedule(self, template: Schedule):
        if not self.schedule_url or self.schedule_url == 'TBD':
            raise ScheduleException('  has no schedule url yet – ignoring')

        url = re.sub(r'^webcal', 'http', self.schedule_url)
        data = requests.get(url, timeout=10).text
        cal = ics.Calendar(data)

        schedule = template.copy(self['name']) or Schedule(conference=self)

        for e in cal.events:
            event = Event(convert_to_dict(e, self), origin=self)
            schedule.add_event(event)

        return schedule
    

def convert_to_dict(e: ics.Event, context: WebcalConference) -> dict:
    title, subtitle, event_type = re.match(r"^(.+?)(?:( ?[:–] .+?))?(?: \((.+?)\))?$", e.name).groups()
    track, = list(e.categories) or [None]
    return {
        "guid": e.uid,
        "title": title,
        "subtitle": subtitle,
        "abstract": e.description,
        "description": '',  # empty description for pretalx importer (temporary workaround)
        "date": e.begin.isoformat(),
        "start": e.begin.format("HH:mm"),
        "duration": format_duration(e.duration),
        "room": e.location or context['name'],
        "persons": [{
            "name": p.common_name,
            "guid": gen_person_uuid(p.email.replace('mailto:', '')),
            # TODO: add p.role?
        } for p in e.attendees],
        "track": track,
        "type": event_type or 'Other',
        "url": e.url or None,
    }


if __name__ == '__main__':
    WebcalConference()