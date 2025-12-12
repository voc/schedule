from os import path, getenv
import requests
from urllib.parse import urlparse

from voc import GenericConference, logger

token = getenv('PRETALX_TOKEN', '')
headers = {'Authorization': 'Token ' + token, 'Content-Type': 'application/json'}

class PretalxConference(GenericConference):
    slug = None
    api_url = ''
    use_token = False

    def __init__(self, url, data, options={}, use_token=False):
        GenericConference.__init__(self, url, data, options)

        if url and url != 'TBD':
            r = urlparse(url)
            self.slug = data.get('slug', path.basename(r.path))

            # /api/events/hip-berlin-2022
            self.api_url = path.join(f"{r.scheme}://{r.netloc}{path.dirname(r.path)}", "api/events", self.slug)

            if use_token:
                self.use_token = True
                if not token:
                    raise Exception("PretalxConference: use_token is True but PRETALX_TOKEN environment variable is not set")
                self.headers = headers
                # cfp.cccv.de uses /api/events/{slug}/schedule/export/schedule.json when using API Token
                # e.g. https://cfp.cccv.de/api/events/39c3/schedule/export/schedule.json
                self.schedule_url = self.api_url + "/schedule/export/schedule.json"
            else:
                self.schedule_url = path.join(url, "schedule/export/schedule.json")

            if 'headers' in options:
                self.headers = options['headers']
                self.headers['Content-Type'] = 'application/json'



            try:
                # load additional metadata via pretalx REST API
                self['meta'] = self.meta()
                self['rooms'] = self.rooms()
            except Exception as e:
                logger.warn(e)
                pass

    def meta(self):
        return requests.get(self.api_url, timeout=self.timeout, headers=self.headers) \
            .json()

    def rooms(self):
        return requests.get(self.api_url + '/rooms', timeout=self.timeout, headers=self.headers) \
            .json() \
            .get('results')

    def latest_schedule(self):
        return requests.get(self.api_url + '/schedules/latest/', timeout=self.timeout, headers=self.headers) \
            .json()
        # Custom pretalx schedule format

    # def tracks(self):
    #    return requests.get(self.api_url + '/tracks', timeout=1, headers=headers) if self.origin_system == 'pretalx.c3voc.de' else {} \
    #        .json() \
    #        .get('results')
