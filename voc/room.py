from dataclasses import dataclass, fields

try:
    from voc.event import Schedule
    from voc.tools import gen_uuid, normalise_string
except:
    from event import Schedule
    from tools import gen_uuid, normalise_string

@dataclass
class Room:
    guid: str = None
    name: str = None
    stream: str = None
    description: str = None
    capacity: int = None
    location: str = None

    _parent: Schedule = None

    @classmethod
    def from_dict(cls, data: dict):
        assert isinstance(data, dict), 'Data must be a dictionary.'

        fieldSet = {f.name for f in fields(cls) if f.init}
        filteredData = {k: v for k, v in data.items() if k in fieldSet}

        return cls(**filteredData)

    def graphql(self):
        return {
            'name': self.name,
            'guid': self.guid or gen_uuid(self.name),
            'description': self.description,
            # 'stream_id': room.stream,
            'slug': normalise_string(self.name.lower()),
            'meta': {'location': self.location},
        }

    # @name.setter
    def update_name(self, new_name: str, update_parent=True):
        if self._parent and update_parent:
            self._parent.rename_rooms({self.name: new_name})
    
        self.name = new_name
