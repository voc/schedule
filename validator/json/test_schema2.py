#!/usr/bin/env -S uv run --quiet --no-project --with pytest --with jsonschema pytest

"""Rule tests for schema2.json.

Each test starts from a valid example (hub = published schedule, halfnarp = DRAFT schedule),
changes one thing, and checks whether the schema accepts or rejects the result.

Run: ./test_schema2.py (needs uv), or: pip install pytest jsonschema && pytest validator/json
"""
import copy
import json
import urllib.request
from functools import cache
from pathlib import Path

import jsonschema
import pytest
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT7

HERE = Path(__file__).parent
SCHEMA = json.loads((HERE / 'schema2.json').read_text())


@cache
def retrieve(uri):
    """Fetch remote $refs (e.g. the GeoJSON schema) explicitly instead of relying on jsonschema's deprecated implicit fetching."""
    with urllib.request.urlopen(uri) as response:
        return Resource.from_contents(json.load(response), default_specification=DRAFT7)


REGISTRY = Registry(retrieve=retrieve)
VALIDATOR = jsonschema.Draft7Validator(SCHEMA, registry=REGISTRY, format_checker=jsonschema.Draft7Validator.FORMAT_CHECKER)


def load(name):
    return json.loads((HERE / 'examples' / name).read_text())


@pytest.fixture
def published():
    return load('hub-schedule2.json')


@pytest.fixture
def draft():
    return load('halfnarp-schedule2.json')


def messages(doc):
    """All error messages, including the ones nested in oneOf/anyOf branches."""
    def walk(errors):
        for e in errors:
            yield e.message
            yield from walk(e.context or [])
    return list(walk(VALIDATOR.iter_errors(doc)))


def assert_valid(doc):
    errors = list(VALIDATOR.iter_errors(doc))
    assert not errors, '\n'.join(f'{e.json_path}: {e.message[:200]}' for e in errors)


def assert_invalid(doc, expected):
    msgs = messages(doc)
    assert msgs, 'expected validation errors, got none'
    assert any(expected in m for m in msgs), f'{expected!r} not in:\n' + '\n'.join(m[:200] for m in msgs)


def test_schema_is_valid_draft7():
    jsonschema.Draft7Validator.check_schema(SCHEMA)


@pytest.mark.parametrize('name', sorted(p.name for p in (HERE / 'examples').glob('*-schedule2.json')))
def test_examples_are_valid(name):
    assert_valid(load(name))


# --- schedule.state / persons ------------------------------------------------

def test_published_schedule_requires_persons(published):
    del published['schedule']['persons']
    assert_invalid(published, "'persons' is a required property")


def test_draft_schedule_may_omit_persons(draft):
    draft['schedule'].pop('persons', None)
    assert_valid(draft)


def test_unknown_schedule_state_is_rejected(published):
    published['schedule']['state'] = 'FOO'
    assert_invalid(published, "'FOO' is not one of")


# --- room / location -----------------------------------------------------------

def test_published_event_requires_room_or_location(published):
    del published['schedule']['events'][0]['room']
    assert_invalid(published, "'room' is a required property")


def test_published_event_with_location_instead_of_room_is_valid(published):
    event = published['schedule']['events'][0]
    del event['room']
    event['location'] = {'name': 'Bar'}
    assert_valid(published)


def test_event_must_not_have_room_and_location(published):
    published['schedule']['events'][0]['location'] = {'name': 'Bar'}
    assert_invalid(published, 'should not be valid under')


def test_draft_schedule_events_need_no_room(draft):
    assert all('room' not in e and 'location' not in e for e in draft['schedule']['events'])
    assert_valid(draft)


def test_draft_event_in_published_schedule_needs_no_room(published):
    event = published['schedule']['events'][0]
    del event['room']
    event['state'] = 'DRAFT'
    assert_valid(published)


def test_room_rule_does_not_depend_on_event_level_check(published):
    """PublishedEvent alone must enforce room/location, so Event needs no own if/then for it."""
    schema = copy.deepcopy(SCHEMA)
    rule = schema['definitions']['Event']['allOf'][0]
    rule.pop('if', None)
    rule.pop('then', None)
    del published['schedule']['events'][0]['room']
    errors = jsonschema.Draft7Validator(schema, registry=REGISTRY).iter_errors(published)

    def walk(errs):
        for e in errs:
            yield e.message
            yield from walk(e.context or [])
    assert "'room' is a required property" in list(walk(errors))


# --- links / participants / languages -------------------------------------------

def test_published_event_requires_links(published):
    del published['schedule']['events'][0]['links']
    assert_invalid(published, "'links' is a required property")


def test_draft_event_may_omit_links(draft):
    draft['schedule']['events'][0].pop('links', None)
    assert_valid(draft)


def test_published_participant_requires_guid(published):
    del published['schedule']['events'][0]['participants'][0]['guid']
    assert_invalid(published, "'guid' is a required property")


def test_draft_participant_may_omit_guid(draft):
    for p in draft['schedule']['events'][0]['participants']:
        p.pop('guid', None)
    assert_valid(draft)


def test_published_event_requires_languages(published):
    del published['schedule']['events'][0]['languages']
    assert_invalid(published, "'languages' is a required property")


def test_languages_may_be_null(published):
    published['schedule']['events'][0]['languages'] = None
    assert_valid(published)


def test_languages_must_be_list_of_codes(published):
    published['schedule']['events'][0]['languages'] = 'en'
    assert_invalid(published, "'en' is not of type 'array', 'null'")


def test_draft_event_may_omit_languages(draft):
    draft['schedule']['events'][0].pop('languages', None)
    assert_valid(draft)


# --- meta events -----------------------------------------------------------------

def test_meta_event_in_published_schedule_needs_no_links_or_room(published):
    published['schedule']['events'].append({
        'type': 'BREAK',
        'title': 'Lunch',
        'start': '2024-12-27T12:00:00+01:00',
        'end': '2024-12-27T13:00:00+01:00',
    })
    assert_valid(published)


# --- event state -------------------------------------------------------------------

def test_unknown_event_state_is_rejected(published):
    published['schedule']['events'][0]['state'] = 'FOO'
    assert_invalid(published, "'FOO' is not valid under any of the given schemas")


# --- start / end / duration --------------------------------------------------------

def test_duration_with_start_and_end_is_rejected(published):
    published['schedule']['events'][0]['duration'] = 'PT30M'
    assert_invalid(published, 'False schema does not allow')


def test_duration_requires_pre_schedule_state(draft):
    del draft['schedule']['events'][0]['state']
    assert_invalid(draft, "'state' is a required property")


def test_duration_with_confirmed_state_is_rejected(draft):
    draft['schedule']['events'][0]['state'] = 'CONFIRMED'
    assert_invalid(draft, "is not one of ['DRAFT', 'SUBMITTED', 'WITHDRAWN', 'ACCEPTED', 'REJECTED']")


def test_duration_with_withdrawn_state_is_valid(draft):
    draft['schedule']['events'][0]['state'] = 'WITHDRAWN'
    assert_valid(draft)


def test_duration_must_be_iso8601(draft):
    draft['schedule']['events'][0]['duration'] = '00:40'
    assert_invalid(draft, 'does not match')
