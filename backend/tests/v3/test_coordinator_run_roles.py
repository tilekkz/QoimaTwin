"""Role grants require actual paid arrival and exact observed exposure partition."""

from dataclasses import replace

import pytest

from app.v3.coordinator_models import CoordinatorEvent
from app.v3.coordinator_run_inventory import InventoryJournal
from app.v3.coordinator_run_motion import MotionJournal
from app.v3.coordinator_run_roles import RoleJournal
from tests.v3.test_coordinator_metrics import role_case
from tests.v3.test_receipt_flow_fixtures import SECOND


def test_role_trace_matches_horizon_and_restoration_without_extra_workers() -> None:
    profile, outcome = role_case(200 * SECOND)
    inventory = InventoryJournal(profile)
    motion = MotionJournal(profile, inventory, outcome.at_horizon.tick)
    roles = RoleJournal(profile, motion)
    cursor = 0
    for state in sorted(
        (*outcome.checkpoints, outcome.at_horizon, outcome.at_end),
        key=lambda row: (row.tick, row.last_seq),
    ):
        while cursor <= state.last_seq:
            event = outcome.events[cursor]
            motion.apply(event)
            roles.apply(event)
            cursor += 1
        roles.check(state)


def test_rehashed_role_view_cannot_activate_before_actual_paid_arrival() -> None:
    profile, outcome = role_case(200 * SECOND)
    inventory = InventoryJournal(profile)
    motion = MotionJournal(profile, inventory, outcome.at_horizon.tick)
    roles = RoleJournal(profile, motion)
    for event in outcome.events:
        motion.apply(event)
        if event.kind == "role_activated":
            assert isinstance(event, CoordinatorEvent)
            assert event.role_view is not None
            wrong = replace(event.role_view, activated_tick=event.tick - 1)
            with pytest.raises(ValueError, match="role"):
                roles.apply(replace(event, role_view=wrong))
            return
        roles.apply(event)
    pytest.fail("Fixture must activate its declared helper")
