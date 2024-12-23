
import argparse
import json
import os
from git import Repo
from voc.c3data import C3data
from voc.event import Event
from voc.schedule import Schedule, ScheduleEncoder
from voc.tools import (
    commit_changes_if_something_relevant_changed,
    git,
)

def export_event_files(schedule: Schedule, options: argparse.Namespace, local = False):
    # to get proper a state, we first have to remove all event files from the previous run
    if not local or options.git:
        git("rm events/*  >/dev/null")
    os.makedirs('events', exist_ok=True)

    # write separate file for each event, to get better git diffs
    # TODO: use Event.export()
    def export_event(event: Event):
        origin_system = None
        if isinstance(event, Event) and event.origin:
            origin_system = event.origin.origin_system

        with open("events/{}.json".format(event["guid"]), "w") as fp:
            json.dump(
                {
                    **event,
                    "room_id": schedule._room_ids.get(event["room"], None),
                    "origin": origin_system or None,
                },
                fp,
                indent=2,
                cls=ScheduleEncoder,
            )

    schedule.foreach_event(export_event)


def postprocessing(schedule: Schedule, options: argparse.Namespace, local = False, targets = []):
    if not local or options.git:
        commit_changes_if_something_relevant_changed(schedule)
        # Attention: This method exits the script, if nothing relevant changed
        # TODO: make this fact more obvious or refactor code

    if not local and "c3data" in targets:
        print("\n== Updating c3data via API…")

        c3data = C3data(schedule)
        c3data.process_changed_events(Repo('.'), options)