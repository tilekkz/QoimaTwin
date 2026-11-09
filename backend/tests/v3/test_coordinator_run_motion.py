"""Every observed actor/cart interval must match declared paid physical steps."""

from dataclasses import replace

import pytest

from app.v3.coordinator_run_inventory import InventoryJournal
from app.v3.coordinator_run_motion import MotionJournal
from tests.v3.test_coordinator_run_inventory import inventory_case


def test_motion_replay_preserves_all_cart_locations_and_paid_return() -> None:
    profile, outcome = inventory_case()
    inventory = InventoryJournal(profile)
    motion = MotionJournal(profile, inventory, outcome.at_horizon.tick)
    cursor = 0
    for state in sorted(
        (*outcome.checkpoints, outcome.at_horizon, outcome.at_end),
        key=lambda row: (row.tick, row.last_seq),
    ):
        while cursor <= state.last_seq:
            event = outcome.events[cursor]
            motion.apply(event)
            inventory.apply(event)
            cursor += 1
        motion.check(state)


def test_paired_start_and_completion_cannot_forge_route_or_paid_duration() -> None:
    profile, outcome = inventory_case()
    inventory = InventoryJournal(profile)
    motion = MotionJournal(profile, inventory, outcome.at_horizon.tick)
    for event in outcome.events:
        operation = event.operation
        if event.kind == "operation_started" and operation is not None and operation.route:
            wrong = replace(operation, planned_end_tick=operation.planned_end_tick + 1)
            with pytest.raises(ValueError, match="declared"):
                motion.apply(replace(event, operation=wrong))
            return
        motion.apply(event)
        inventory.apply(event)
    pytest.fail("Fixture must include actual positive paid movement")


def test_open_actor_cannot_start_another_operation() -> None:
    profile, outcome = inventory_case()
    inventory = InventoryJournal(profile)
    motion = MotionJournal(profile, inventory, outcome.at_horizon.tick)
    for event in outcome.events:
        motion.apply(event)
        inventory.apply(event)
        if event.kind == "operation_started":
            with pytest.raises(ValueError, match="overlap"):
                motion.apply(event)
            return
    pytest.fail("Fixture must start an actual actor operation")
