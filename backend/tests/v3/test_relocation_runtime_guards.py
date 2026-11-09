"""Adversarial hand checks of retained authority, custody, and atomic resource promises."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.relocation_engine import RelocationEngine
from app.v3.relocation_observe import RelocationOutcome
from app.v3.relocation_runtime import dispatch
from tests.v3.test_receipt_flow_fixtures import receipt_conveyor
from tests.v3.test_relocation_runtime_fixtures import SECOND, relocation_hand


@pytest.mark.parametrize(
    "mutation", ["operation", "steps", "profile", "capability", "place", "derived", "paid"]
)
def test_retained_runtime_mutation_is_rejected(mutation: str) -> None:
    engine = RelocationEngine(relocation_hand(), receipt_conveyor())
    engine.run(SECOND, 6 * SECOND)
    worker = engine.workers["S01"]
    if mutation == "operation":
        assert worker.operation is not None
        worker.operation = replace(worker.operation, planned_end_tick=1)
    elif mutation == "steps":
        worker.steps[0] = replace(worker.steps[0], duration=1)
    elif mutation == "profile":
        object.__setattr__(engine.relocation_profile.jobs[0], "take_ticks", 1)
    elif mutation == "capability":
        engine.capabilities["S01"] = replace(
            engine.capabilities["S01"], eligible_roles=("ship", "pack")
        )
    elif mutation == "place":
        engine.whole_places["target"] = replace(engine.whole_places["target"], node_id="SLOT")
    elif mutation == "paid":
        worker.closed_paid = 0
    else:
        engine.derived_sources["HU1"] = "target"
    with pytest.raises(RuntimeError, match="RELOCATION"):
        engine._check()


def test_ledger_transfer_does_not_replace_completed_take_authority() -> None:
    engine = RelocationEngine(relocation_hand(), receipt_conveyor())
    engine.run(SECOND, 3 * SECOND)
    engine.ledger.transfer_whole_hu(
        "invalid-early-take",
        engine.ledger.revision,
        "HU1",
        "actor:S01",
        claim_id="relocation:N1",
    )
    with pytest.raises(RuntimeError, match="RELOCATION_CUSTODY"):
        engine._check()


@pytest.mark.parametrize(
    "conflict", ["stock", "receipt_target", "whole_target", "packing", "receipt_worker"]
)
def test_atomic_admission_conflict_adds_no_partial_relocation_resources(conflict: str) -> None:
    engine = RelocationEngine(relocation_hand(), receipt_conveyor())
    engine.horizon = 20 * SECOND
    engine.relocations["N1"].status = "waiting"
    if conflict == "stock":
        engine.ledger.reserve_hu("foreign", "foreign-job", engine.ledger.revision, "HU1")
    elif conflict in {"receipt_target", "whole_target"}:
        engine.leases[conflict.split("_")[0] + ":place:target"] = "other"
    elif conflict == "packing":
        engine.workers["S01"].order_id, engine.workers["S01"].task = "other", "packer"
    else:
        engine.leases["receipt:worker:S01"] = "other"
    before_claims, before_leases = engine.ledger.claims, dict(engine.leases)
    dispatch(engine)
    assert engine.ledger.claims == before_claims and engine.leases == before_leases
    assert engine.relocations["N1"].admitted_tick is None


def test_claim_and_leases_remain_until_one_tick_before_paid_return() -> None:
    engine = RelocationEngine(relocation_hand(), receipt_conveyor())
    result = engine.run(SECOND, 13 * SECOND - 1)
    assert len(result.at_end.leases) == 3
    engine.ledger.release_claim("relocation:N1", "N1")
    with pytest.raises(RuntimeError, match="RELOCATION_EXACT_CLAIM"):
        engine._check()


def test_admission_respects_future_worker_break_and_does_not_start_unpaid_pause() -> None:
    from app.v3.staff_registry_models import Unavailability

    profile = relocation_hand()
    registry = replace(
        profile.coordinator.registry,
        unavailability=(Unavailability("S01", 5 * SECOND, 10 * SECOND, "hand-break"),),
    )
    profile = replace(profile, coordinator=replace(profile.coordinator, registry=registry))
    engine = RelocationEngine(profile, receipt_conveyor())
    result = engine.run(20 * SECOND, 30 * SECOND)
    assert isinstance(result, RelocationOutcome)
    assert result.at_end.relocations[0].admitted_tick == 10 * SECOND
    assert result.at_end.relocations[0].returned_tick == 23 * SECOND


def test_gross_mass_per_sku_and_all_original_identities_are_conserved() -> None:
    engine = RelocationEngine(relocation_hand(), receipt_conveyor())
    before = engine.ledger.balance(), engine.ledger.snapshot().locations
    engine.run(10 * SECOND, 20 * SECOND)
    assert engine.ledger.balance() == before[0]
    assert engine.ledger.snapshot().locations == before[1]
    assert engine.ledger.contents("HU1").gross_mass_kg == F(127, 20)


@pytest.mark.parametrize(
    "part",
    ["actor_speed", "actor_available", "step", "route", "paid", "claim_bool", "claim_duplicate"],
)
def test_numeric_type_alias_and_duplicate_claim_cannot_retain_authority(part: str) -> None:
    engine = RelocationEngine(relocation_hand(), receipt_conveyor())
    engine.run(2 * SECOND, 6 * SECOND)
    engine._check()
    worker = engine.workers["S01"]
    if part in {"actor_speed", "actor_available"}:
        worker.spec = replace(worker.spec)
        object.__setattr__(
            worker.spec,
            "speed_m_s" if part == "actor_speed" else "available_tick",
            1 if part == "actor_speed" else False,
        )
    elif part == "step":
        worker.steps[0] = replace(worker.steps[0])
        object.__setattr__(worker.steps[0], "duration", F(worker.steps[0].duration))
    elif part == "route":
        assert worker.operation is not None and worker.operation.route is not None
        route = replace(worker.operation.route)
        object.__setattr__(route, "length_m", 3)
        worker.operation = replace(worker.operation, route=route)
    elif part == "paid":
        object.__setattr__(worker, "closed_paid", F(worker.closed_paid))
    else:
        claim = replace(engine.ledger.claims[0])
        value: object = 1 if part == "claim_bool" else (*claim.unit_ids, claim.unit_ids[0])
        object.__setattr__(claim, "whole_hu" if part == "claim_bool" else "unit_ids", value)
        engine.ledger._claims._values[claim.claim_id] = claim
    with pytest.raises((RuntimeError, ValueError)):
        engine._check()
