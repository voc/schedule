import re
import json
import collections
from collections import OrderedDict
import dateutil.parser
from datetime import datetime, timedelta

from voc.tools import str2timedelta

class EventSourceInterface:
    origin_system = None


class Schedule(EventSourceInterface):
    pass


class Event(collections.abc.Mapping):
    _event = None
    origin: EventSourceInterface = None
    start: datetime = None
    duration: timedelta = None

    def __init__(self, data, start_time: datetime = None, origin: EventSourceInterface = None):
        # when being restored from single event file, we have to specially process the origin attribute
        if 'origin' in data:
            self.origin = EventSourceInterface()
            self.origin.origin_system = data['origin']
            del data['origin']

        # remove empty optional fields – and url... Does anybody remember why `url`, too?
        for field in ["video_download_url", "answers", "url"]:
            if field in data and not (data[field]):
                del data[field]

        assert 'id' in data or data.get('guid'), "guid (or id) is required"
        assert 'title' in data
        assert 'date' in data

        self.start = start_time or dateutil.parser.parse(data["date"])
        self.duration = str2timedelta(data["duration"])

        if 'start' not in data:
            data['start'] = self.start.strftime('%H:%M')

        # empty description for pretalx importer (temporary workaround)
        if 'description' not in data:
            data['description'] = ''

        self._event = OrderedDict(data)

        # generate id from guid, when not set so old apps can still process this event
        if 'id' not in data and 'guid' in data:
            from voc.tools import get_id
            self._event['id'] = get_id(self['guid'], length=4)
        self.origin = origin

    @property
    def end(self):
        return self.start + self.duration

    def __getitem__(self, key):
        return self._event.get(key)

    def __setitem__(self, key, value):
        self._event[key] = value

    def __iter__(self):
        return self._event.__iter__()

    def __len__(self):
        return len(self._event)

    def items(self):
        return self._event.items()

    def persons(self):
        return [p.get("name", p.get("public_name")) for p in self._event["persons"]]

    def json(self):
        return self._event

    def graphql(self):
        r = dict(
            (re.sub(r"_([a-z])", lambda m: (m.group(1).upper()), k), v)
            for k, v in self._event.items()
        )
        r["localId"] = self._event["id"]
        del r["id"]
        r["eventType"] = self._event["type"]
        del r["type"]
        del r["room"]
        del r["start"]
        r["startDate"] = self._event["date"]
        del r["date"]
        duration = self._event["duration"].split(":")
        r["duration"] = {"hours": int(duration[0]), "minutes": int(duration[1])}
        del r["persons"]
        if "recording" in r:
            if r["recording"].get("optout") is True:
                r["do_not_record"] = True
            del r["recording"]
        if "videoDownloadUrl" in r:
            del r["videoDownloadUrl"]
        if "answers" in r:
            del r["answers"]
        # fix wrong formatted links
        if "links" in r and len(r["links"]) > 0 and isinstance(r["links"][0], str):
            r["links"] = [{"url": url, "title": url} for url in r["links"]]
        return r

    def voctoimport(self):
        r = dict(self._event.items())
        r["talkid"] = self._event["id"]
        del r["id"]
        del r["type"]
        del r["start"]
        del r["persons"]
        del r["logo"]
        del r["subtitle"]
        if "recording_license" in r:
            del r["recording_license"]
        if "recording" in r:
            del r["recording"]
        if "do_not_record" in r:
            del r["do_not_record"]
        if "video_download_url" in r:
            del r["video_download_url"]
        if "answers" in r:
            del r["answers"]
        if "links" in r:
            del r["links"]
        if "attachments" in r:
            del r["attachments"]
        return r

    # export all attributes which are not part of rC3 core event model
    def meta(self):
        r = OrderedDict(self._event.items())
        # r['local_id'] = self._event['id']
        # del r["id"]
        del r["guid"]
        del r["slug"]
        del r["room"]
        del r["start"]
        del r["date"]
        del r["duration"]
        del r["track_id"]
        del r["track"]
        # del r['persons']
        # if 'answers' in r:
        #    del r['answers']
        # fix wrong formatted links
        if len(r["links"]) > 0 and isinstance(r["links"][0], str):
            r["links"] = [{"url": url, "title": url} for url in r["links"]]
        return r

    def __str__(self):
        return json.dumps(self._event, indent=2)

    def export(self, prefix, suffix=""):
        with open("{}{}{}.json".format(prefix, self._event["guid"], suffix), "w") as fp:
            json.dump(self._event, fp, indent=2)
