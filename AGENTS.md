# AGENTS.md

This file provides guidance to AI coding agents when working with code in this repository.

## What This Repo Is

`c3voc-schedule-tools` — a mono-repo of scripts and a library (`voc/`) to generate, convert, and validate conference "schedule" files (schedule.json / schedule.xml) for events using pretalx, frab, or any other system that can export schedule.json/CSV. Originally built for Chaos Computer Club (C3VOC) events. Published to PyPI as `c3voc-schedule-tools`.

## Setup

Any of these work; `uv` is the currently preferred flow:

```sh
brew install python uv
uv sync                 # runtime deps
uv sync --group dev     # + flake8 for linting
uv run python schedule_39C3.py   # run a script without activating the venv
```

Poetry (`poetry install`) and plain pip (`pip3 install -r requirements.txt`) are also supported — `pyproject.toml` is the poetry-core build source of truth, `requirements.txt` is a plain mirror of the same deps.

## Commands

- **Lint**: `uv run flake8` (config in `pyproject.toml`: `E501` ignored, max line length 150, `voc/__init__.py` allowed unused imports).
- **Run an event script**: `uv run python schedule_<EVENT>.py [--task X] [--online] [--git] [--fail] [--debug] [--stats]` (options defined via `optparse` in `voc/tools.py:DefaultOptionParser` / each script's own parser).
- **Validate schedule.json against schema**:
  ```sh
  pip install check-jsonschema
  check-jsonschema --schemafile validator/json/schema2.json validator/json/examples/hub-schedule2.json   # v2 schema (in development)
  check-jsonschema --schemafile validator/json/schema.json  validator/json/examples/pretalx-democon.json # v1 schema
  ```
  or `cd validator/json && ./validate_schedule_json.sh` to run both against the checked-in examples.
- **Validate schedule.xml against XSD**: `validator/xsd/validate_schedule_xml.sh <url-or-local-file>` (requires `xmllint`, `curl`).
- **pre-commit**: `.pre-commit-config.yaml` runs `check-jsonschema --id-metaschema` on every `validator/json/*.json` file — run `pre-commit install` once to wire it up.
- There is no Python unit test suite. `validator/test.sh` is a smoke test that XML-validates a live congress URL; CI (`.github/workflows/validate.yml`) is the JSON-schema validation described above, triggered on any `**.json` change.
- **Release**: pushing a GitHub release triggers `.github/workflows/publish.yml`, which sets the poetry version from the git tag, builds, and publishes to PyPI via trusted publishing (no manual version bump needed).

## Architecture

### `voc/` — the library package (what gets published to PyPI)

- `schedule.py` — the central data model: `Schedule(dict)`, `ScheduleDay(dict)`, `ScheduleStats`, `ScheduleEncoder`, `ScheduleException`. Schedules are dict-backed and JSON-serializable by construction.
- `event.py` — `EventSourceInterface` and the generic `Event[T = dict[str, Any]](Mapping)`, parameterized over the underlying representation. JSON-backed events use `dict`; XML-backed events use `ElementTree` via `schedulexml.py`'s `EventXML(Event[ElementTree])`.
- `schedulexml.py` — `ScheduleXML`/`EventXML`: an XML-backed implementation of the same `Schedule`/`Event` abstractions, for producing/consuming schedule.xml.
- Conference data sources implementing `EventSourceInterface`/`GenericConference`: `generic.py` (base, generic JSON schedule API), `pretalx.py` (`PretalxConference`), `webcal.py` (`WebcalConference`, `ics`-based iCal v1), `webcal2.py` (`WebcalConference2`, `icalendar`-based, newer). Per-script code picks whichever source(s) it needs and merges them into one `Schedule`.
- External publishing/import integrations: `c3data.py` (GraphQL API for c3voc's own conference database — create/get conference, add/remove room & event, `C3data`/`upsert_schedule`), `rc3hub.py` (REST-ish push/depublish to an rc3 hub instance), `voctoimport.py` (`VoctoImport`, pushes events into the VOC import tool).
- `tools.py` — shared plumbing used by nearly every top-level script: `DefaultOptionParser`, GUID/short-id generation (`gen_uuid`, `get_id`, SoS-id persistence), string/time normalization, `foreach_event`, schedule filtering/export (`export_filtered_schedule`), and `commit_changes_if_something_relevant_changed` (git commit helper).
- `git.py` — exports per-event files from a `Schedule` and does git postprocessing (used by scripts that commit generated schedules to a repo, e.g. for `data.c3voc.de`).
- `room.py` — `Room` value object (name/guid/description/char). `logger.py` — `Logger`/`configure_logging`.

### `locations/`

Per-venue `Room` definitions (e.g. `cch.py:CCH.Rooms`) that event scripts import instead of redefining room GUIDs inline.

### Top-level `schedule_<EVENT>.py` scripts

One script per conference/event (`schedule_39C3.py`, `schedule_camp2023.py`, `schedule_rC3.py`, …) — the actual "apps" built on `voc/`. Typical shape: parse options via `optparse`, pull talks from `PretalxConference`/`GenericConference`, attach rooms from `locations/`, assemble a `Schedule`, then export/push via `voc.tools`, `voc.git`, and/or `voc.c3data`/`voc.rc3hub`. `archive/` holds retired scripts for past events (32C3–35C3, asm16, camp15, etc.) — not maintained, kept for reference.

### Standalone converters (not part of `voc/`)

`csv2schedule_deu.py`, `wiki2schedule*.py`, `wikitable2schedule.py`, `xhtml2schedule.py`, `html2schedule.py`, `html2meta.py`, `filter_xcal.py`, `schedule_json2xml.py`, `schedule_transform.py`, `import.py` — one-off input/output format converters, largely independent of each other.

### `validator/` — schema definitions, no Python

- `json/schema.json` — schedule v1 JSON Schema. `json/schema2.json` — schedule v2 (in-progress rewrite, draft-06, currently at `"version": "alpha-4"`; this branch (`schedule2`) is actively iterating on it — see recent commits for field additions like `sameAs`/`partOf` URIs, ATPROTO link relation, track `name`/`slug` requirements). Examples live in `json/examples/`.
- `submission-json/` — separate schema for pretalx/frab submission export (`submission.json`/`person.json`), independent of the schedule schema.
- `xsd/` — `schedule.xml.xsd` (full) and `schedule-without-person.xml.xsd` (variant), validated via `validate_schedule_xml.sh`.
- `web_validator/` — small standalone Sinatra (Ruby) web app (`webapp.rb`, `config.ru`, `Gemfile`) for validating schedule.xml online; unrelated to the Python tooling.


## LLM Usage Policy

Using an LLM to help write code is fine. Reviewers just might want to know when it happened, so they can weigh the review accordingly — code that reads unusually verbose, follows an unfamiliar pattern, or touches a lot of files at once often has an LLM behind it, and reviewers benefit from knowing that up front.

**Rule:** if an LLM generated a substantial part of a commit (not just autocomplete or minor suggestions), add a trailer to the commit message:

```
Assisted-by: LLM
```

- Use the generic `LLM` value — don't name the specific product/vendor. The point is disclosure to reviewers, not advertising a tool.
- Trivial LLM use (autocomplete, one-line suggestions, creating commit messages from staged changes, boilerplate you'd have typed anyway) doesn't need a trailer. 
- You're still fully responsible for the code you commit. Review, understand, and test it before committing it under your name, regardless of how it was produced.

### Example

```
fix(lib): handle nil schedule in conference import

Assisted-by: LLM
```
