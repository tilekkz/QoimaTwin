"""Prewritten partial-state claim authority, before a future pick can reveal corruption."""

from dataclasses import replace

import pytest

from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.coordinator_models import CoordinatorSnapshot
from app.v3.coordinator_run import build_coordinator_run
from app.v3.coordinator_run_inputs import freeze_hand_inputs
from app.v3.light_flow_models import FlowEvent
from tests.v3.test_coordinator_multi_fixtures import multi_profile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor


def _without_claim(
    point: CoordinatorSnapshot,
    events: tuple[FlowEvent, ...],
) -> CoordinatorSnapshot:
    return replace(
        point,
        last_seq=sum(e.tick <= point.tick for e in events) - 1,
        inventory=replace(point.inventory, claims=(), claim_generation=0),
    )


def test_partial_mid_pick_cannot_drop_the_actual_admitted_unit_claim() -> None:
    profile, source = multi_profile(candidate=False), receipt_conveyor()
    inputs = freeze_hand_inputs(profile, source, 84 * SECOND, 84 * SECOND)
    outcome = CoordinatorEngine(profile, source).run(84 * SECOND, 84 * SECOND)
    build_coordinator_run(inputs, outcome)
    operation = next(w.operation for w in outcome.at_end.workers if w.actor_id == "P01")
    assert operation is not None and operation.kind == "pick"
    assert (operation.start_tick, operation.planned_end_tick) == (83 * SECOND, 86 * SECOND)
    assert {c.claim_id for c in outcome.at_end.inventory.claims} == {"pick:O1"}
    events = tuple(
        replace(event, seq=index)
        for index, event in enumerate(
            e for e in outcome.events if e.kind != "inventory_claim_acquired"
        )
    )
    wrong = replace(
        outcome,
        events=events,
        at_horizon=_without_claim(outcome.at_horizon, events),
        at_end=_without_claim(outcome.at_end, events),
        checkpoints=tuple(_without_claim(point, events) for point in outcome.checkpoints),
    )
    with pytest.raises(ValueError):
        build_coordinator_run(inputs, wrong)
