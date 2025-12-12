# C3VOC Schedule Tools

[![PyPI version](https://badge.fury.io/py/c3voc-schedule-tools.svg)](https://badge.fury.io/py/c3voc-schedule-tools)
[![License: EUPL-1.2](https://img.shields.io/badge/License-EUPL--1.2-blue.svg)](https://joinup.ec.europa.eu/collection/eupl/eupl-text-eupl-12)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

A Python library for generating, converting, and validating [schedule files](https://c3voc.de/wiki/schedule) for conferences and events.

Originally developed for the Chaos Computer Club events (C3), this library supports multiple schedule formats and conference management systems including [pretalx](https://github.com/pretalx/pretalx), [frab](https://frab.github.io/frab/).
## Features

- **Integration**: Direct integration with pretalx, frab, and other conference planning systems
- **Schedule Validation**: Built-in validation against schedule XML schema
- **Flexible Data Sources**: Support for web APIs, local files, and custom data sources
- **Multiple Converters**: Built-in converters for various data sources and formats

## Installation

```bash
pip install c3voc-schedule-tools
```

## Quick Start

### Basic Schedule Creation

```python
from voc import Schedule, Event, Room

# Create a new schedule
schedule = Schedule.from_template(
    name="My Conference 2024",
    conference_title="My Conference",
    conference_acronym="mc24",
    start_day=25,
    days_count=3,
    timezone="Europe/Berlin"
)

# Add rooms, generate your own global unique ids e.g. via `uuidgen`
schedule.add_rooms([
    {"name": "Main Hall", "guid": "67D04C40-B35A-496A-A31C-C0F3FF63DAB7"},
    {"name": "Workshop Room", "guid": "5564FBA9-DBB5-4B6B-A0F0-CCF6C9F1EBD7"}
])

# Add an event
event = Event({
    "id": "event-1",
    "title": "Opening Keynote",
    "abstract": "Welcome to the conference",
    "date": "2024-12-25T10:00:00+01:00",
    "duration": "01:00",
    "room": "Main Hall",
    "track": "Keynotes",
    "type": "lecture",
    "language": "en",
    "persons": [{"public_name": "Jane Doe"}]
})
schedule.add_event(event)

# Export to JSON
schedule.export('schedule.json')
```

### Loading from Pretalx

```python
from voc import PretalxConference, Schedule

# Load conference data from pretalx
conference = PretalxConference(
    url="https://pretalx.example.com/event/my-conference/",
    data={"name": "My Conference"}
)

# Get the schedule
schedule = conference.schedule()

# Modify / Filter / etc
…

# Export to different formats
schedule.export('schedule.json')
schedule.export('schedule.xml')
```

### Working with Existing Schedules

```python
from voc import Schedule

# Load from URL
schedule = Schedule.from_url("https://example.com/schedule.json")

# Load from file
schedule = Schedule.from_file("schedule.json")

# Filter events by track
track_events = schedule.events(filter=lambda e: e.get('track') == 'Security')

# Get all rooms
rooms = schedule.rooms()

# Get events for a specific day
day_1_events = schedule.day(1).events()
```


## API Reference

### Core Classes

#### Schedule

The main schedule container that holds conference metadata, days, rooms, and events.

**Key Methods:**

- `Schedule.from_url(url)` - Load schedule from URL
- `Schedule.from_file(path)` - Load schedule from file
- `Schedule.from_template(...)` - Create from template
- `add_event(event)` - Add an event to the schedule
- `add_rooms(rooms)` - Add rooms to the schedule
- `export(filename)` - Export to file
- `validate()` - Validate against XML schema


#### Event

Represents a single conference event/talk.

**Properties:**

- `guid` - Global unique event identifier
- `id` - Local event identifier, deprecated
- `title` - Event title
- `abstract` - Event description
- `date` - Start date/time
- `duration` - Event duration
- `room` - Room name
- `track` - Track/category
- `persons` - List of speakers


#### Room

Represents a conference room / lecture hall / etc.

**Properties:**

- `name` - Room name
- `guid` - Global unique room identifier


### Conference Planning Systems

#### PretalxConference

Integration with pretalx conference management system.

```python
conference = PretalxConference(
    url="https://pretalx.example.com/event/",
    data={"name": "Conference Name"}
)
schedule = conference.schedule()
```

#### GenericConference

Base class for generic conference data sources.

```python
conference = GenericConference(
    url="https://example.com/schedule.json",
    data={"name": "Conference Name"}
)
```

#### WebcalConference

Import from iCal/webcal sources.

```python
from voc import WebcalConference

conference = WebcalConference(url="https://example.com/events.ics")
schedule = conference.schedule(template_schedule)
```


## Supported Formats

### Input Formats

- **JSON**: schedule.json format
- **iCal**: RFC 5545 iCalendar format
- **Pretalx API**: Direct API integration
- **CSV**: Custom CSV formats (see examples in [parent folder](https://github.com/voc/schedule/blob/master/csv2schedule_deu.py))

### Output Formats

- **JSON**: C3VOC schedule.json
- **XML**: CCC / Frab schedule XML aka [vnd.c3voc.schedule+xml](https://www.iana.org/assignments/media-types/application/vnd.c3voc.schedule+xml)
- **iCal**: RFC 5545 format (TODO?)


## Configuration

### Environment Variables

- `PRETALX_TOKEN` - API token for pretalx integration
- `C3DATA_API_URL` - C3data API endpoint
- `C3DATA_TOKEN` - C3data authentication token

### Validation

The library includes built-in validation against the schedule XML schema:

```python
# Validate a schedule
try:
    schedule.validate()
    print("Schedule is valid")
except ScheduleException as e:
    print(f"Validation error: {e}")
```

## Examples

TBD, see parent folder

## License

This project is licensed under the EUPL-1.2 License - see the [LICENSE](LICENSE) file for details.

## Links

- [Documentation](https://c3voc.de/wiki/schedule)
- [PyPI Package](https://pypi.org/project/c3voc-schedule-tools/)
- [Source Code](https://github.com/voc/schedule)
- [Issue Tracker](https://github.com/voc/schedule/issues)
