"""Hand assertions precede the N1 runtime implementation; no source-scale run is used."""

from dataclasses import replace

import pytest

from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.relocation_engine import RelocationEngine
from app.v3.relocation_observe import RelocationOutcome
from tests.v3.test_receipt_flow_fixtures import receipt_conveyor
from tests.v3.test_relocation_runtime_fixtures import SECOND, relocation_hand


def test_paid_intact_relocation_has_two_real_transfers_and_paid_return() -> None:
    profile = relocation_hand()
    engine = RelocationEngine(profile, receipt_conveyor())
    result = engine.run(10 * SECOND, 20 * SECOND)
    assert isinstance(result, RelocationOutcome)
    state = result.at_end.relocations[0]
    assert result.status == "complete"
    assert (state.admitted_tick, state.taken_tick, state.placed_tick, state.returned_tick) == (
        0,
        4 * SECOND,
        8 * SECOND,
        13 * SECOND,
    )
    assert result.business_complete_tick == 8 * SECOND
    assert result.resource_drained_tick == 13 * SECOND
    worker = next(w for w in result.at_end.workers if w.actor_id == "S01")
    assert worker.paid_ticks == 13 * SECOND
    assert worker.node == "SH" and worker.order_id is None
    assert engine.ledger.contents("HU1").container.owner_id == "target"
    assert engine.ledger.claims == () and result.at_end.leases == ()
    deltas = [e.delta for e in result.events if e.order_id == "N1" and e.delta]
    assert [d.operation for d in deltas] == ["transfer_whole_hu", "transfer_whole_hu"]
    assert all(set(d.unit_ids) == {f"U{i}" for i in range(1, 25)} for d in deltas)
    assert profile.coordinator.world.receipts.flow.stock.containers[0].owner_id == "slot"


@pytest.mark.parametrize(
    ("cap", "owner", "taken", "placed"),
    [
        (3 * SECOND, "slot", None, None),
        (6 * SECOND, "actor:S01", 4 * SECOND, None),
        (9 * SECOND, "target", 4 * SECOND, 8 * SECOND),
        (13 * SECOND - 1, "target", 4 * SECOND, 8 * SECOND),
    ],
)
def test_caps_preserve_actual_custody_and_all_reservations(
    cap: int,
    owner: str,
    taken: int | None,
    placed: int | None,
) -> None:
    engine = RelocationEngine(relocation_hand(), receipt_conveyor())
    result = engine.run(SECOND, cap)
    assert isinstance(result, RelocationOutcome)
    state = result.at_end.relocations[0]
    assert result.status == "partial"
    assert (state.taken_tick, state.placed_tick, state.returned_tick) == (taken, placed, None)
    assert engine.ledger.contents("HU1").container.owner_id == owner
    assert len(engine.ledger.claims) == 1
    assert engine.ledger.claims[0].claim_id == "relocation:N1"
    assert dict(result.at_end.leases) == {
        "relocation:worker:S01": "N1",
        "relocation:place:target": "N1",
        "relocation:hu:HU1": "N1",
    }
    assert result.resource_drained_tick is None


def test_no_jobs_preserves_coordinator_events_and_observations() -> None:
    profile = replace(relocation_hand(), jobs=())
    expected = CoordinatorEngine(profile.coordinator, receipt_conveyor()).run(SECOND, 2 * SECOND)
    actual = RelocationEngine(profile, receipt_conveyor()).run(SECOND, 2 * SECOND)
    assert actual == expected


def test_no_jobs_cannot_override_existing_whole_source_descriptors() -> None:
    profile = relocation_hand(whole_arrival=0)
    profile = replace(
        profile, jobs=(), places=tuple(replace(p, node_id="TARGET") for p in profile.places)
    )
    expected = CoordinatorEngine(profile.coordinator, receipt_conveyor()).run(SECOND, 100 * SECOND)
    actual = RelocationEngine(profile, receipt_conveyor()).run(SECOND, 100 * SECOND)
    assert actual == expected


def test_relocated_whole_order_uses_completed_target_as_its_actual_source() -> None:
    engine = RelocationEngine(relocation_hand(whole_arrival=SECOND), receipt_conveyor())
    result = engine.run(20 * SECOND, 100 * SECOND)
    assert result.status == "complete"
    assert engine.whole_sources["W1"] == "target"
    approach = next(
        e.operation for e in result.events if e.order_id == "W1" and e.kind == "operation_started"
    )
    assert approach is not None and approach.target_node == "TARGET"
    admitted = next(s for s in result.at_end.whole_orders if s.job_id == "W1").admitted_tick
    assert admitted is not None and admitted >= 13 * SECOND


def test_whole_claim_first_keeps_relocation_unadmitted_without_extra_claim() -> None:
    profile = relocation_hand(whole_arrival=0)
    profile = replace(profile, jobs=(replace(profile.jobs[0], arrival_tick=SECOND),))
    engine = RelocationEngine(profile, receipt_conveyor())
    result = engine.run(10 * SECOND, 12 * SECOND)
    assert isinstance(result, RelocationOutcome)
    state = result.at_end.relocations[0]
    assert state.admitted_tick is None and state.wait_reason in {"stock_claimed", "source_moved"}
    assert not any(c.claim_id.startswith("relocation:") for c in engine.ledger.claims)
    assert not any(k.startswith("relocation:") for k in engine.leases)


def test_altered_derived_source_is_rejected() -> None:
    engine = RelocationEngine(relocation_hand(whole_arrival=SECOND), receipt_conveyor())
    engine.run(10 * SECOND, 12 * SECOND)
    engine.whole_sources["W1"] = "slot"
    with pytest.raises(RuntimeError, match="RELOCATION"):
        engine._check()


def test_small_intact_hu_uses_the_same_paid_physical_custody() -> None:
    engine = RelocationEngine(relocation_hand(standard=False), receipt_conveyor())
    result = engine.run(10 * SECOND, 20 * SECOND)
    assert isinstance(result, RelocationOutcome)
    assert result.at_end.relocations[0].returned_tick == 13 * SECOND
    assert engine.ledger.contents("HU1").container.owner_id == "target"


@pytest.mark.parametrize(
    ("cap", "owner", "done"),
    [
        (4 * SECOND, "actor:S01", False),
        (8 * SECOND, "target", False),
        (13 * SECOND, "target", True),
    ],
)
def test_exact_operation_end_is_included_at_horizon(cap: int, owner: str, done: bool) -> None:
    engine = RelocationEngine(relocation_hand(), receipt_conveyor())
    result = engine.run(cap, cap)
    assert engine.ledger.contents("HU1").container.owner_id == owner
    assert (result.status == "complete") == done
    assert (len(engine.ledger.claims) == 0) == done


def test_zero_distance_steps_still_require_two_positive_handlings() -> None:
    profile = relocation_hand()
    flow = profile.coordinator.world.receipts.flow
    flow = replace(
        flow,
        actors=tuple(replace(a, home="SLOT") if a.actor_id == "S01" else a for a in flow.actors),
    )
    world = replace(
        profile.coordinator.world, receipts=replace(profile.coordinator.world.receipts, flow=flow)
    )
    profile = replace(
        profile,
        coordinator=replace(profile.coordinator, world=world),
        places=tuple(replace(p, node_id="SLOT") for p in profile.places),
    )
    engine = RelocationEngine(profile, receipt_conveyor())
    result = engine.run(SECOND, 4 * SECOND)
    assert isinstance(result, RelocationOutcome)
    state = result.at_end.relocations[0]
    assert (state.taken_tick, state.placed_tick, state.returned_tick) == (
        2 * SECOND,
        3 * SECOND,
        3 * SECOND,
    )
    assert next(w for w in result.at_end.workers if w.actor_id == "S01").paid_ticks == 3 * SECOND
