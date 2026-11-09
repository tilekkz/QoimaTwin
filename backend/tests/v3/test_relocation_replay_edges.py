"""Partial caps, delayed admission, and downstream whole work share the same prefix ledger."""

from dataclasses import replace

import pytest

from app.v3.interface import Json
from app.v3.relocation_engine import RelocationEngine
from app.v3.relocation_models import RelocationProfile
from app.v3.relocation_run import build_relocation_run
from app.v3.relocation_run_inputs import freeze_hand_inputs
from tests.v3.test_receipt_flow_fixtures import receipt_conveyor
from tests.v3.test_relocation_replay import read
from tests.v3.test_relocation_runtime_fixtures import SECOND, relocation_hand


def recorded(profile: RelocationProfile, horizon: int, cap: int) -> tuple[Json, bytes]:
    inputs = freeze_hand_inputs(profile, receipt_conveyor(), horizon, cap)
    result = RelocationEngine(profile, receipt_conveyor()).run(horizon, cap)
    return build_relocation_run(inputs, result), inputs.frozen_bytes


@pytest.mark.parametrize("cap", [3 * SECOND, 6 * SECOND, 9 * SECOND])
def test_partial_reader_retains_exact_observed_claim_and_future_is_unavailable(cap: int) -> None:
    run, inputs = recorded(relocation_hand(), SECOND, cap)
    frame = read(run, inputs, cap)
    assert run["status"] == "partial"
    assert frame["snapshot"] == run["outcome"]["at_end"]
    assert len(frame["snapshot"]["inventory"]["claims"]) == 1
    assert len(frame["snapshot"]["leases"]) == 3
    with pytest.raises(ValueError, match="unobserved"):
        read(run, inputs, cap + 1)


def test_before_arrival_has_no_future_admission_or_reserved_stock() -> None:
    profile = relocation_hand()
    profile = replace(profile, jobs=(replace(profile.jobs[0], arrival_tick=2 * SECOND),))
    run, inputs = recorded(profile, 10 * SECOND, 20 * SECOND)
    point = read(run, inputs, SECOND)["snapshot"]
    assert point["relocations"][0]["status"] == "unreleased"
    assert point["relocations"][0]["admitted_tick"] is None
    assert point["derived_sources"] == []
    assert point["inventory"]["claims"] == [] and point["leases"] == []
    assert all(w["paid_ticks"] == 0 for w in point["workers"])


def test_whole_after_return_uses_new_source_with_only_its_own_claim() -> None:
    run, inputs = recorded(relocation_hand(whole_arrival=SECOND), 20 * SECOND, 100 * SECOND)
    point = read(run, inputs, 14 * SECOND)["snapshot"]
    claim = point["inventory"]["claims"]
    assert len(claim) == 1 and claim[0]["job_id"] == "W1"
    assert point["derived_sources"] == [["HU1", "target"]]
    worker = next(w for w in point["workers"] if w["actor_id"] == "S01")
    assert worker["operation"]["target_node"] == "TARGET"
    assert point["relocations"][0]["returned_tick"] == 13 * SECOND
    assert read(run, inputs, run["observed_until_tick"])["snapshot"] == run["outcome"]["at_end"]


def test_zero_travel_steps_are_already_settled_without_interpolation() -> None:
    profile = relocation_hand()
    world, flow = profile.coordinator.world, profile.coordinator.world.receipts.flow
    actors = tuple(replace(a, home="SLOT") if a.actor_id == "S01" else a for a in flow.actors)
    world = replace(world, receipts=replace(world.receipts, flow=replace(flow, actors=actors)))
    profile = replace(
        profile,
        coordinator=replace(profile.coordinator, world=world),
        places=tuple(replace(p, node_id="SLOT") for p in profile.places),
    )
    run, inputs = recorded(profile, SECOND, 4 * SECOND)
    during = read(run, inputs, 2 * SECOND)["snapshot"]
    assert during["relocations"][0]["completed_steps"] == 3
    worker = next(w for w in during["workers"] if w["actor_id"] == "S01")
    assert worker["operation"]["kind"] == "relocation_place"
    assert worker["node"] == "SLOT"
    done = read(run, inputs, 3 * SECOND)["snapshot"]
    assert done["relocations"][0]["returned_tick"] == 3 * SECOND
    assert done["inventory"]["claims"] == [] and done["leases"] == []
