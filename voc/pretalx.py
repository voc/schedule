from os import path, getenv
import requests
from urllib.parse import urlparse

from voc import GenericConference, logger

headers = {'Authorization': 'Token ' + getenv('PRETALX_TOKEN', ''), 'Content-Type': 'application/json'}


class PretalxConference(GenericConference):
    slug = None
    api_url = None

    def __init__(self, url, data, options={}):
        GenericConference.__init__(self, url, data, options)

        if url and url != 'TBD':
            self.schedule_url = path.join(url, "schedule/export/schedule.json")
            r = urlparse(url)
            self.slug = data.get('slug', path.basename(r.path))

            # /api/events/hip-berlin-2022
            self.api_url = path.join(f"{r.scheme}://{r.netloc}{path.dirname(r.path)}", "api/events", self.slug)

            try:
                # load additional metadata via pretalx REST API
                self['meta'] = self.meta()
                self['rooms'] = self.rooms()
            except Exception as e:
                logger.warn(e)
                pass

    def meta(self):
        return requests.get(self.api_url, timeout=self.timeout) \
            .json()

    def rooms(self):
        return requests.get(self.api_url + '/rooms', timeout=self.timeout, headers=headers if self.origin_system == 'pretalx.c3voc.de' else {'Content-Type': 'application/json'}) \
            .json() \
            .get('results')

    def latest_schedule(self):
        return requests.get(self.api_url + '/schedules/latest/', timeout=self.timeout) \
            .json()
        # Custom pretalx schedule format

    # def tracks(self):
    #    return requests.get(self.api_url + '/tracks', timeout=1, headers=headers) if self.origin_system == 'pretalx.c3voc.de' else {} \
    #        .json() \
    #        .get('results')
