from os import path, getenv
from urllib.parse import urlparse
import requests

from voc import GenericConference

headers = {'Authorization': 'Token ' + getenv('PRETALX_TOKEN', ''), 'Content-Type': 'application/json'}


class PretalxConference(GenericConference):
    slug = None
    api_url = None

    def __init__(self, url, data, options={}):
        GenericConference.__init__(self, url, data, options)
        
        if url and url != 'TBD':
            self.schedule_url = url + "/schedule/export/schedule.json"
            r = urlparse(url)
            self.slug = data.get('slug', path.basename(r.path))

            # /api/events/hip-berlin-2022
            self.api_url = path.join(f"{r.scheme}://{r.netloc}{path.dirname(r.path)}", "api/events", self.slug)

            # load additional metadata via pretalx REST API
            self['meta'] = self.meta()
            self['rooms'] = self.rooms()

    def meta(self):
        return requests.get(self.api_url, timeout=1) \
            .json()

    def rooms(self):
        return requests.get(self.api_url + '/rooms', timeout=1, headers=headers) \
            .json() \
            .get('results')