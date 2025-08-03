# C3VOC Schedule Tools

[![PyPI version](https://badge.fury.io/py/c3voc-schedule-tools.svg)](https://badge.fury.io/py/c3voc-schedule-tools)
[![License: EUPL-1.2](https://img.shields.io/badge/License-EUPL--1.2-blue.svg)](https://joinup.ec.europa.eu/collection/eupl/eupl-text-eupl-12)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

A Python library for generating, converting, and validating [schedule files](https://c3voc.de/wiki/schedule) for conferences and events. Originally developed for the Chaos Computer Club events (C3), this library supports multiple schedule formats and conference management systems including [pretalx](https://github.com/pretalx/pretalx), [frab](https://frab.github.io/frab/), and others that can generate schedule.json or CSV files.

## Features

- **Integration**: Direct integration with pretalx, frab, and other conference management systems
- **Schedule Validation**: Built-in validation against schedule XML schema
- **Flexible Data Sources**: Support for web APIs, local files, and custom data sources
- **Multiple Converters**: Built-in converters for various data sources and formats

## Installation

```bash
pip install c3voc-schedule-tools
```

### Development Installation

```bash
git clone https://github.com/voc/schedule.git
cd schedule
pip install -e .
```

## Quick Start

### Basic Schedule Creation

```python
from voc import Schedule, Event, Room

# Create a new schedule
schedule = Schedule.from_template(
    name="My Conference 2024",
    conference_title="My Conference",
    conference_acronym="MC24",
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
