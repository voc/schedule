from dataclasses import dataclass


@dataclass
class Room:
    guid: str = None
    name: str = None
    stream: str = None
