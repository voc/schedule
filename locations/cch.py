from voc import Room

class CCH:
    name = "Congress Center Hamburg"
    short_name = "CCH"
    timezone = "Europe/Berlin"
    latitude = 53.5587
    longitude = 9.9916
    address = "Mittelweg 1, 20148 Hamburg, Germany"
    website = "https://www.cch.de/"

    class Rooms:
        S1   = Room(name='Saal One',     guid='ba692ba3-421b-5371-8309-60acc34a3c05', char='O')
        SZ   = Room(name='Saal Zero',    guid='62251a07-13e4-5a72-bb3c-8528416ee0f2', char='Z')
        SG   = Room(name='Saal Ground',  guid='7202df07-050c-552f-8318-992f94e40ef0', char='G')
        SF   = Room(name='Saal Fuse',    guid='85a6ba5d-11d9-4efe-8d28-c5f7165a19ce', char='F')
        SX07 = Room(name='Saal X 07',    guid='9001b61b-b1f1-5bcd-89fd-135ed5e43e20', char='X')
        STH  = Room(name='SoS Stage H',  guid='9001b61b-b1f1-5bcd-89fd-135ed5e43e42', char='H')
        CLUB = Room(name='Club',         guid='9001b61b-b1f1-5bcd-89fd-135ed5e43e21', char='C')
        S10  = Room(name="Speakersdesk", guid="9001b61b-b1f1-5bcd-89fd-135ed5e43e10", char="SD")
        R313 = Room(name='Raum 313',     description='C3VOC Coworking', guid='a5b0b1c5-2872-48ee-a7ef-80252af0f76d', char='VC')
        R314 = Room(name='Raum 314',     description='C3VOC Office', guid='a5b0b1c5-2872-48ee-a7ef-80252af0f76c', char='VO')
        R315 = Room(name='Raum 315',     description='C3VOC Hel(l|p)desk', guid='a5b0b1c5-2872-48ee-a7ef-80252af0f76b', char='VHD')
        E    = Room(name='Everywhere',   guid='7abcfbfd-4b2f-4fc4-8e6c-6ff854d4936f', char='∀')
