#!/usr/bin/env -S uv run --quiet --no-project --with pytest --with jsonschema pytest

"""Rule tests for schema.json (schedule v1, draft-06).

Each test starts from the valid pretalx-democon example, changes one thing,
and checks whether the schema accepts or rejects the result.

Run: ./test_schema1.py (needs uv), or: pip install pytest jsonschema && pytest validator/json
"""
import json
from pathlib import Path

import jsonschema
import pytest

HERE = Path(__file__).parent
SCHEMA = json.loads((HERE / 'schema.json').read_text())
VALIDATOR = jsonschema.Draft6Validator(SCHEMA, format_checker=jsonschema.Draft6Validator.FORMAT_CHECKER)


def load(name):
    return json.loads((HERE / 'examples' / name).read_text())


@pytest.fixture
def doc():
    return load('pretalx-democon.json')


def conference(doc):
    return doc['schedule']['conference']


def day(doc):
    return conference(doc)['days'][0]


def event(doc):
    return next(iter(day(doc)['rooms'].values()))[0]


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


def test_schema_is_valid_draft6():
    jsonschema.Draft6Validator.check_schema(SCHEMA)


def test_pretalx_democon_example_is_valid():
    assert_valid(load('pretalx-democon.json'))


def error_kinds(doc):
    """Distinct (path, error) pairs, with list indices and room names replaced by '*'."""
    def walk(errors):
        for e in errors:
            if e.context:
                yield from walk(e.context)
            else:
                yield e

    kinds = set()
    for e in walk(VALIDATOR.iter_errors(doc)):
        path = list(e.path)
        if path[:3] == ['schedule', 'conference', 'days'] and len(path) > 5:
            path[5] = '*'
        path = '/'.join('*' if isinstance(p, int) else p for p in path)
        kinds.add((path, e.message if e.validator == 'additionalProperties' else e.validator))
    return kinds


EVENT = 'schedule/conference/days/*/rooms/*/*'


@pytest.mark.parametrize('name, expected', [
    ('pretalx-rc3.json', {
        (EVENT, "Additional properties are not allowed ('answers' was unexpected)"),
        (f'{EVENT}/slug', 'pattern'),  # pretalx codes like 'MJA8QY'
        ('schedule/conference/acronym', 'pattern'),  # 'rc3-channels-2020'
    }),
    ('frab-camp2019.json', {
        (f'{EVENT}/slug', 'pattern'),  # 'Camp2019-10386-opening_ceremony'
        ('schedule/conference/acronym', 'pattern'),  # 'Camp2019'
    }),
])
def test_known_invalid_examples(name, expected):
    """These real-world exports are known to violate the schema; fail if the set of violations changes."""
    assert error_kinds(load(name)) == expected


# --- top level / schedule ------------------------------------------------------

def test_schedule_is_required(doc):
    del doc['schedule']
    assert_invalid(doc, "'schedule' is a required property")


def test_unknown_top_level_property_is_rejected(doc):
    doc['foo'] = 1
    assert_invalid(doc, 'Additional properties are not allowed')


@pytest.mark.parametrize('field', ['conference', 'version'])
def test_schedule_required_fields(doc, field):
    del doc['schedule'][field]
    assert_invalid(doc, f"'{field}' is a required property")


def test_schedule_allows_additional_properties(doc):
    doc['schedule']['foo'] = 1
    assert_valid(doc)


# --- conference ------------------------------------------------------------------

@pytest.mark.parametrize('field', ['title', 'acronym', 'days', 'daysCount', 'start', 'end', 'timeslot_duration'])
def test_conference_required_fields(doc, field):
    del conference(doc)[field]
    assert_invalid(doc, f"'{field}' is a required property")


def test_unknown_conference_property_is_rejected(doc):
    conference(doc)['foo'] = 1
    assert_invalid(doc, 'Additional properties are not allowed')


@pytest.mark.parametrize('acronym', SCHEMA['definitions']['Conference']['properties']['acronym']['examples'] + ['jev22', 'camp2023'])
def test_valid_acronyms(doc, acronym):
    conference(doc)['acronym'] = acronym
    assert_valid(doc)


@pytest.mark.parametrize('acronym', ['36C3', 'ab', 'with space'])
def test_invalid_acronyms(doc, acronym):
    conference(doc)['acronym'] = acronym
    assert_invalid(doc, 'does not match')


def test_invalid_time_zone_name_is_rejected(doc):
    conference(doc)['time_zone_name'] = 'europe/berlin'
    assert_invalid(doc, 'does not match')


def test_days_count_must_be_integer(doc):
    conference(doc)['daysCount'] = '3'
    assert_invalid(doc, "'3' is not of type 'integer'")


# --- days ------------------------------------------------------------------------

@pytest.mark.parametrize('field', ['date', 'day_end', 'day_start', 'index', 'rooms'])
def test_day_required_fields(doc, field):
    del day(doc)[field]
    assert_invalid(doc, f"'{field}' is a required property")


def test_day_rooms_must_contain_event_lists(doc):
    day(doc)['rooms']['Gray Room'] = {}
    assert_invalid(doc, "{} is not of type 'array'")


# --- rooms -----------------------------------------------------------------------

@pytest.mark.parametrize('field', ['name', 'guid'])
def test_room_required_fields(doc, field):
    del conference(doc)['rooms'][0][field]
    assert_invalid(doc, f"'{field}' is a required property")


def test_unknown_room_property_is_rejected(doc):
    conference(doc)['rooms'][0]['foo'] = 1
    assert_invalid(doc, "'foo' does not match any of the regexes")


def test_localized_room_description_is_allowed(doc):
    conference(doc)['rooms'][0]['description_de'] = 'Grauer Raum'
    assert_valid(doc)


# --- events ----------------------------------------------------------------------

@pytest.mark.parametrize('field', SCHEMA['definitions']['Event']['required'])
def test_event_required_fields(doc, field):
    del event(doc)[field]
    assert_invalid(doc, f"'{field}' is a required property")


def test_unknown_event_property_is_rejected(doc):
    event(doc)['foo'] = 1
    assert_invalid(doc, 'Additional properties are not allowed')


@pytest.mark.parametrize('field', ['language', 'track', 'do_not_record'])
def test_event_nullable_fields(doc, field):
    event(doc)[field] = None
    assert_valid(doc)


@pytest.mark.parametrize('field, value', [
    ('start', '9:00'),
    ('start', '24:00'),
    ('duration', '30'),
    ('duration', 'PT30M'),
    ('slug', 'Has-Uppercase'),
    ('slug', 'trailing-dash-'),
])
def test_event_field_patterns(doc, field, value):
    event(doc)[field] = value
    assert_invalid(doc, 'does not match')


def test_event_id_must_be_positive(doc):
    event(doc)['id'] = 0
    assert_invalid(doc, '0 is less than the minimum of 1')


# --- persons ---------------------------------------------------------------------

def test_frab_person_is_valid(doc):
    event(doc)['persons'] = [{'id': 1, 'public_name': 'Alice'}]
    assert_valid(doc)


def test_pretalx_person_is_valid(doc):
    event(doc)['persons'] = [{'name': 'Alice', 'code': 'ABC123'}]
    assert_valid(doc)


def test_person_needs_name_or_frab_fields(doc):
    event(doc)['persons'] = [{'guid': 'b379c473-93b9-4eae-9a09-d482e86cede3'}]
    assert_invalid(doc, 'is not valid under any of the given schemas')


# --- links -----------------------------------------------------------------------

def test_link_requires_url(doc):
    event(doc)['links'] = [{'title': 'Slides'}]
    assert_invalid(doc, "'url' is a required property")


def test_link_type_must_be_known(doc):
    event(doc)['links'] = [{'url': 'https://example.org/', 'type': 'video'}]
    assert_invalid(doc, "'video' is not one of")


def test_unknown_link_property_is_rejected(doc):
    event(doc)['links'] = [{'url': 'https://example.org/', 'foo': 1}]
    assert_invalid(doc, 'Additional properties are not allowed')
