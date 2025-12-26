from enum import Flag, auto

from voc import Room


class Rooms(Flag):
    E = auto()
    S1 = auto(),
    SZ = auto(),
    SG = auto(),
    SF = auto(),
    SX07 = auto(),
    STH = auto(),
    CLUB = auto(),
    S10 = auto(),
    R313 = auto(),
    R314 = auto(),
    R315  = auto()

room_list = {
    Rooms.S1: Room(name='One', guid='ba692ba3-421b-5371-8309-60acc34a3c08', char='O'),
    Rooms.SG: Room(name='Ground', guid='7202df07-050c-552f-8318-992f94e40ef3', char='G'),
    Rooms.SZ: Room(name='Zero', guid='62251a07-13e4-5a72-bb3c-8528416ee0f5', char='Z'),
    Rooms.SF: Room(name='Fuse', guid='e58b284a-d3e6-42cc-be2b-7e02c791bf98', char='F'),
    Rooms.SX07: Room(name='Saal X 07', guid='9001b61b-b1f1-5bcd-89fd-135ed5e43e20', char='X'),
    Rooms.STH: Room(name='SoS Stage H', guid='9001b61b-b1f1-5bcd-89fd-135ed5e43e42', char='H'),
    Rooms.CLUB:Room(name='Club', guid='9001b61b-b1f1-5bcd-89fd-135ed5e43e21', char='C'),
    Rooms.R315: Room(name='Raum 315', description='C3VOC Hel(l|p)desk', guid='a5b0b1c5-2872-48ee-a7ef-80252af0f76b', char='VHD'),
    Rooms.R314: Room(name='Raum 314', description='C3VOC Office', guid='a5b0b1c5-2872-48ee-a7ef-80252af0f76c', char='VO'),
    Rooms.R313: Room(name='Raum 313', description='C3VOC Coworking', guid='a5b0b1c5-2872-48ee-a7ef-80252af0f76d', char='VC'),
    Rooms.S10: Room(name="Saal 10", guid="9001b61b-b1f1-5bcd-89fd-135ed5e43e10", char="SD"),
    Rooms.E: Room(name='Everywhere', guid='7abcfbfd-4b2f-4fc4-8e6c-6ff854d4936f', char='∀')
}
