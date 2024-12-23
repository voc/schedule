from voc.event import EventSourceInterface
from .schedule import Schedule, ScheduleException
from urllib.parse import urlparse


class GenericConference(dict, EventSourceInterface):
    schedule_url = None
    options = {}
    timeout = 10

    def __init__(self, url, data, options={}):
        self.origin_system = urlparse(url).netloc
        self.schedule_url = url
        self.options = options
        self['url'] = url
        dict.__init__(self, data)

    def __str__(self):
        return self['name']

    def schedule(self, *args) -> Schedule:
        if not self.schedule_url or self.schedule_url == 'TBD':
            raise ScheduleException('  has no schedule url yet – ignoring')

        return Schedule.from_url(self.schedule_url, self.timeout)
