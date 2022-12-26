from dataclasses import dataclass, fields

from voc.tools import gen_uuid, normalise_string


@dataclass
class Room:
    guid: str = None
    name: str = None
    stream: str = None
    description: str = None
    capacity: int = None
    location: str = None

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