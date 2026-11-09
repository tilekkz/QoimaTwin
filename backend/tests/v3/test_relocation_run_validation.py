"""Independent causal corruption cases; scheduler is forbidden during reader validation."""

from dataclasses import replace
from functools import cache
from hashlib import sha256
from unittest.mock import patch

import pytest

from app.storage.canonical_json import canonical_bytes
from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.coordinator_models import CoordinatorOutcome
from app.v3.light_flow_engine import LightFlowEngine
from app.v3.light_flow_models import FlowEvent
from app.v3.relocation_engine import RelocationEngine
from app.v3.relocation_models import RelocationProfile
from app.v3.relocation_native_projection import project_outcome
from app.v3.relocation_observe import RelocationEvent, RelocationOutcome, RelocationSnapshot
from app.v3.relocation_run_validation import validate_relocation_outcome
from tests.v3.test_receipt_flow_fixtures import receipt_conveyor
from tests.v3.test_relocation_runtime_fixtures import SECOND, relocation_hand


@cache
def recorded(
    cap: int = 20 * SECOND, whole: bool = False
) -> tuple[RelocationProfile, RelocationOutcome]:
    profile = relocation_hand(whole_arrival=SECOND if whole else None)
    horizon = 20 * SECOND if whole else min(10 * SECOND, cap)
    result = RelocationEngine(profile, receipt_conveyor()).run(horizon, cap)
    assert isinstance(result, RelocationOutcome)
    return profile, result


def validate(
    profile: RelocationProfile, outcome: CoordinatorOutcome, horizon: int, cap: int
) -> None:
    with (
        patch.object(
            RelocationEngine, "run", side_effect=AssertionError("Reader executed scheduler")
        ),
        patch.object(
            LightFlowEngine, "run", side_effect=AssertionError("Reader executed base scheduler")
        ),
        patch.object(
            CoordinatorEngine,
            "__init__",
            side_effect=AssertionError("Reader constructed scheduler"),
        ),
    ):
        validate_relocation_outcome(profile, receipt_conveyor(), outcome, horizon, cap)


@pytest.mark.parametrize(
    "cap",
    [3 * SECOND, 4 * SECOND, 6 * SECOND, 8 * SECOND, 13 * SECOND - 1, 13 * SECOND, 20 * SECOND],
)
def test_replay_preserves_independent_partial_custody_and_paid_return(cap: int) -> None:
    profile, outcome = recorded(cap)
    validate(profile, outcome, min(10 * SECOND, cap), cap)


def test_replay_uses_actual_relocated_source_for_later_whole_job() -> None:
    profile, outcome = recorded(100 * SECOND, True)
    validate(profile, outcome, 20 * SECOND, 100 * SECOND)


@pytest.mark.parametrize(
    "kind",
    [
        "relocation_taken",
        "relocation_placed",
        "inventory_claim_acquired",
        "inventory_claim_released",
        "relocation_returned",
    ],
)
def test_missing_causal_fact_is_rejected_even_after_sequence_and_capture_repair(kind: str) -> None:
    profile, outcome = recorded()
    rows = tuple(e for e in outcome.events if not (e.order_id == "N1" and e.kind == kind))
    altered = resequence(outcome, rows)
    with pytest.raises(ValueError):
        validate(profile, altered, 10 * SECOND, 20 * SECOND)


@pytest.mark.parametrize(
    "mutation",
    [
        "route",
        "actor",
        "destination",
        "effect_clock",
        "phase",
        "claim_units",
        "release_early",
        "extra_resource",
        "paid",
        "derived",
    ],
)
def test_consistent_outer_shape_cannot_authorize_false_inner_history(mutation: str) -> None:
    profile, outcome = recorded()
    altered = corrupt(outcome, mutation)
    original_hash = sha256(canonical_bytes(project_outcome(profile.coordinator, outcome))).digest()
    forged_hash = sha256(canonical_bytes(project_outcome(profile.coordinator, altered))).digest()
    assert forged_hash != original_hash
    with pytest.raises(ValueError):
        validate(profile, altered, 10 * SECOND, 20 * SECOND)


def resequence(outcome: RelocationOutcome, rows: tuple[FlowEvent, ...]) -> RelocationOutcome:
    events = tuple(replace(e, seq=i) for i, e in enumerate(rows))

    def capture(value: RelocationSnapshot) -> RelocationSnapshot:
        return replace(value, last_seq=sum(e.tick <= value.tick for e in events) - 1)

    return replace(
        outcome,
        events=events,
        at_horizon=capture(outcome.at_horizon),
        at_end=capture(outcome.at_end),
        checkpoints=tuple(capture(s) for s in outcome.checkpoints),
    )


def corrupt(outcome: RelocationOutcome, mutation: str) -> RelocationOutcome:
    if mutation in {"paid", "derived"}:
        state = outcome.at_end
        if mutation == "paid":
            state = replace(
                state,
                workers=tuple(
                    replace(w, paid_ticks=0) if w.actor_id == "S01" else w for w in state.workers
                ),
            )
        else:
            state = replace(state, derived_sources=(("HU1", "slot"),))
        return replace(outcome, at_end=state)
    rows = list(outcome.events)
    for i, row in enumerate(rows):
        assert isinstance(row, RelocationEvent)
        changed = change_event(row, mutation)
        if changed is not None:
            rows[i] = changed
            return resequence(outcome, tuple(rows))
    raise AssertionError("Missing corruption target")


def change_event(event: RelocationEvent, mutation: str) -> RelocationEvent | None:
    if mutation == "route" and event.kind == "operation_started" and event.operation is not None:
        route = event.operation.route
        assert route is not None
        return replace(
            event, operation=replace(event.operation, route=replace(route, arc_ids=("invented",)))
        )
    if mutation == "actor" and event.kind == "relocation_admitted":
        return replace(event, actor_id="S02")
    if mutation in {"destination", "effect_clock", "phase"} and event.kind == "relocation_placed":
        assert event.relocation is not None
        if mutation == "effect_clock":
            return replace(event, tick=event.tick - 1)
        view = (
            replace(event.relocation, destination_owner="slot")
            if mutation == "destination"
            else replace(event.relocation, completed_steps=2)
        )
        return replace(event, relocation=view)
    if mutation == "claim_units" and event.inventory_claim is not None:
        return replace(event, inventory_claim=replace(event.inventory_claim, unit_ids=("U1",)))
    if mutation == "release_early" and event.kind == "inventory_claim_released":
        return replace(event, tick=8 * SECOND)
    if mutation == "extra_resource" and event.kind == "relocation_resource_acquired":
        return replace(event, resource_id="relocation:place:slot")
    return None
