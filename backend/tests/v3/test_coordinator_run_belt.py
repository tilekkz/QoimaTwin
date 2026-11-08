"""Native C belt capture derives from declared physical plans, not interpolated event guesses."""

from dataclasses import replace

import pytest

from app.v3.coordinator_run_belt import BeltJournal
from app.v3.coordinator_run_inventory import InventoryJournal
from tests.v3.test_coordinator_run_inventory import inventory_case
from tests.v3.test_receipt_flow_fixtures import receipt_conveyor


def test_actual_belt_captures_preserve_pack_replacement_and_bounded_queues() -> None:
    profile, outcome = inventory_case()
    inventory = InventoryJournal(profile)
    journal = BeltJournal(receipt_conveyor(), inventory)
    cursor = 0
    for state in sorted(
        (*outcome.checkpoints, outcome.at_horizon, outcome.at_end),
        key=lambda row: (row.tick, row.last_seq),
    ):
        while cursor <= state.last_seq:
            event = outcome.events[cursor]
            inventory.apply(event)
            journal.apply(event)
            cursor += 1
        journal.check(state)
    assert outcome.at_end.belt.completed == 2


def test_rehashed_belt_start_cannot_invent_a_different_source_speed() -> None:
    profile, outcome = inventory_case()
    inventory = InventoryJournal(profile)
    journal = BeltJournal(receipt_conveyor(), inventory)
    for event in outcome.events:
        inventory.apply(event)
        belt = event.belt_event
        if belt is not None and belt.kind == "motion_started":
            assert belt.planned_end_tick is not None
            wrong = replace(belt, planned_end_tick=belt.planned_end_tick + 1)
            with pytest.raises(ValueError, match="compiled"):
                journal.apply(replace(event, belt_event=wrong))
            return
        journal.apply(event)
    pytest.fail("Fixture must move an actual carrier on the source belt")
