"""Additional N1 replay boundaries preserve base physics and exact public input types."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.relocation_engine import RelocationEngine
from app.v3.relocation_observe import RelocationEvent, RelocationOutcome
from tests.v3.test_receipt_flow_fixtures import receipt_conveyor
from tests.v3.test_relocation_run_validation import recorded, resequence, validate
from tests.v3.test_relocation_runtime_fixtures import SECOND, relocation_hand


def test_empty_extension_replays_original_exact_base_outcome() -> None:
    profile = replace(relocation_hand(), jobs=())
    result = RelocationEngine(profile, receipt_conveyor()).run(SECOND, 2 * SECOND)
    validate(profile, result, SECOND, 2 * SECOND)


def test_whole_first_wait_retains_original_goods_replay_and_no_relocation_claim() -> None:
    profile = relocation_hand(whole_arrival=0)
    profile = replace(profile, jobs=(replace(profile.jobs[0], arrival_tick=SECOND),))
    result = RelocationEngine(profile, receipt_conveyor()).run(10 * SECOND, 12 * SECOND)
    validate(profile, result, 10 * SECOND, 12 * SECOND)


def test_zero_distance_progress_requires_no_invented_positive_motion() -> None:
    profile = relocation_hand()
    world = profile.coordinator.world
    flow = world.receipts.flow
    actors = tuple(replace(a, home="SLOT") if a.actor_id == "S01" else a for a in flow.actors)
    world = replace(world, receipts=replace(world.receipts, flow=replace(flow, actors=actors)))
    profile = replace(
        profile,
        coordinator=replace(profile.coordinator, world=world),
        places=tuple(replace(p, node_id="SLOT") for p in profile.places),
    )
    result = RelocationEngine(profile, receipt_conveyor()).run(SECOND, 4 * SECOND)
    validate(profile, result, SECOND, 4 * SECOND)


@pytest.mark.parametrize("part", ["bool_tick", "bool_claim", "fraction_paid", "duplicate_claim"])
def test_direct_public_validator_rejects_scalar_aliases_and_duplicate_ids(part: str) -> None:
    profile, outcome = recorded()
    if part == "fraction_paid":
        state = outcome.at_end
        workers = tuple(replace(w) for w in state.workers)
        worker = next(w for w in workers if w.actor_id == "S01")
        object.__setattr__(worker, "paid_ticks", F(worker.paid_ticks))
        altered = replace(outcome, at_end=replace(state, workers=workers))
    else:
        events = list(outcome.events)
        index = next(
            i
            for i, e in enumerate(events)
            if isinstance(e, RelocationEvent) and e.inventory_claim is not None
        )
        row = events[index]
        assert isinstance(row, RelocationEvent) and row.inventory_claim is not None
        row = replace(row, inventory_claim=replace(row.inventory_claim))
        assert row.inventory_claim is not None
        if part == "bool_tick":
            object.__setattr__(row, "tick", False)
        elif part == "bool_claim":
            object.__setattr__(row.inventory_claim, "whole_hu", 1)
        else:
            object.__setattr__(
                row.inventory_claim, "unit_ids", (*row.inventory_claim.unit_ids, "U1")
            )
        events[index] = row
        altered = replace(outcome, events=tuple(events))
    with pytest.raises(ValueError):
        validate(profile, altered, 10 * SECOND, 20 * SECOND)


@pytest.mark.parametrize("part", ["balance", "exposure", "lease"])
def test_base_capture_authority_remains_active_for_nonempty_extension(part: str) -> None:
    profile, outcome = recorded(6 * SECOND)
    state = outcome.at_end
    if part == "balance":
        state = replace(state, balance=replace(state.balance, onsite_mass_kg=F(0)))
    elif part == "exposure":
        state = replace(state, exposure=replace(state.exposure, transition_ticks=1))
    else:
        state = replace(state, leases=state.leases[:-1])
    with pytest.raises(ValueError):
        validate(profile, replace(outcome, at_end=state), 6 * SECOND, 6 * SECOND)


def test_missing_base_whole_resource_fact_is_not_filtered_out_by_extension() -> None:
    profile, outcome = recorded(100 * SECOND, True)
    rows = tuple(
        e
        for e in outcome.events
        if not (e.order_id == "W1" and e.kind == "whole_resource_acquired")
    )
    with pytest.raises(ValueError):
        validate(profile, resequence(outcome, rows), 20 * SECOND, 100 * SECOND)


def test_base_whole_cannot_reuse_old_source_plan_after_relocation() -> None:
    profile, outcome = recorded(100 * SECOND, True)
    rows = list(outcome.events)
    index = next(
        i for i, e in enumerate(rows) if e.order_id == "W1" and e.kind == "operation_started"
    )
    event = rows[index]
    assert event.operation is not None
    rows[index] = replace(event, operation=replace(event.operation, target_node="SLOT"))
    with pytest.raises(ValueError):
        validate(profile, replace(outcome, events=tuple(rows)), 20 * SECOND, 100 * SECOND)


def test_noop_discriminator_does_not_promote_nonempty_extension_outcome() -> None:
    profile, outcome = recorded()
    assert isinstance(outcome, RelocationOutcome)
    with pytest.raises(ValueError):
        validate(replace(profile, jobs=()), outcome, 10 * SECOND, 20 * SECOND)
