"""Receipt credit and putaway need both claim facts, including before the next operation."""

from dataclasses import replace

import pytest

from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.coordinator_run_effects import validate_effects
from tests.v3.test_coordinator_shared_world import receipt_profile_at
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor


@pytest.mark.parametrize("kind", ["inventory_claim_acquired", "inventory_claim_released"])
def test_receipt_physical_handover_cannot_omit_its_required_claim_fact(kind: str) -> None:
    profile = receipt_profile_at()
    outcome = CoordinatorEngine(profile, receipt_conveyor()).run(30 * SECOND, 40 * SECOND)
    validate_effects(profile, outcome.events, 30 * SECOND, outcome.at_end.tick)
    receipt = outcome.at_end.receipts[0]
    assert (receipt.credited_tick, receipt.placed_tick, receipt.returned_tick) == (
        12 * SECOND,
        23 * SECOND,
        33 * SECOND,
    )
    assert sum(event.kind == kind for event in outcome.events) == 1
    missing = tuple(event for event in outcome.events if event.kind != kind)
    with pytest.raises(ValueError, match="claim"):
        validate_effects(profile, missing, 30 * SECOND, outcome.at_end.tick)
    delayed = tuple(
        replace(event, tick=event.tick + 1) if event.kind == kind else event
        for event in outcome.events
    )
    with pytest.raises(ValueError, match="claim"):
        validate_effects(profile, delayed, 30 * SECOND, outcome.at_end.tick)
