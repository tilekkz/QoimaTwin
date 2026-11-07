"""Proposed 2.1 contract: no mutation of the shared v2.0 schema."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import pytest

from app.contracts.loader import ContractBundle
from app.exporter.proposal import export_proposal, validate_proposal
from app.simulation.engine import Engine
from app.simulation.fixtures import fixture_inputs, load_fixture
from app.storage.canonical_json import sha256_hex


@pytest.fixture(scope="session")
def proposal(bundle: ContractBundle, contracts_dir: Path) -> dict[str, Any]:
    inputs = fixture_inputs(bundle, load_fixture(contracts_dir))
    inputs = dataclasses.replace(
        inputs, scenario=inputs.scenario.model_copy(update={"horizon_s": 10.0})
    )
    engine = Engine(inputs, check_invariants=True)
    return export_proposal(engine, engine.run())


def test_proposal_identity_and_windows(proposal: dict[str, Any]) -> None:
    assert proposal["schema_version"] == "2.1"
    assert proposal["contract_status"] == "proposal"
    assert proposal["run_id"] == sha256_hex(proposal["identity"])
    assert len(proposal["input_hashes"]) == 9
    assert proposal["ended_at_s"] == 474.0
    assert proposal["metrics"]["at_horizon"]["dispatched_total"] == 0
    assert proposal["metrics"]["at_end"]["dispatched_total"] == 1
    assert proposal["pre_shift"] is None
    assert proposal["relocation_plan_id"] is None


def test_proposal_transfers_are_single_typed_records(proposal: dict[str, Any]) -> None:
    kinds = {event["kind"] for event in proposal["events"]}
    assert "cell_moved" in kinds
    assert not {"cell_entered", "cell_exited"} & kinds
    for seq, event in enumerate(proposal["events"]):
        assert event["seq"] == seq
        assert event["at_tick"] == round(event["at_s"] * proposal["ticks_per_second"])
        assert "at_tick" not in event["payload"]


def test_proposal_snapshots_have_public_watermarks(proposal: dict[str, Any]) -> None:
    for snapshot in proposal["snapshots"]:
        assert "timers" not in snapshot["state"]
        assert "checkpoint" not in snapshot["state"]
        assert snapshot["state_hash"] == sha256_hex(snapshot["state"])
        last = max(
            (e["seq"] for e in proposal["events"] if e["at_tick"] <= snapshot["at_tick"]),
            default=-1,
        )
        assert snapshot["last_seq"] == last


def test_proposal_forklift_operations_and_carrying(proposal: dict[str, Any]) -> None:
    forklift = [a for a in proposal["actions"] if a["actor_id"] == "F02"]
    assert [a["operation"] for a in forklift] == [
        "travel_empty",
        "load",
        "travel_loaded",
        "unload",
        "travel_empty",
    ]
    assert forklift[0]["carrying_cargo_id"] is None
    assert forklift[2]["carrying_cargo_id"] == "PAL0001"
    assert forklift[-1]["carrying_cargo_id"] is None
    attached = [e for e in proposal["events"] if e["kind"] == "cargo_attached"]
    assert any(e["payload"]["cargo_id"] == "PAL0001" for e in attached)


def test_proposal_rejects_payload_typos(proposal: dict[str, Any]) -> None:
    import copy

    altered = copy.deepcopy(proposal)
    event = next(e for e in altered["events"] if e["kind"] == "cell_moved")
    event["payload"]["from_typo"] = event["payload"].pop("from")
    with pytest.raises(ValueError, match="payload"):
        validate_proposal(altered)


def test_proposal_has_explicit_pallet_places(proposal: dict[str, Any]) -> None:
    locations = {p["container_id"]: p for p in proposal["locations"]}
    assert locations["OPEN_PALLET"]["positions"] == [[64.92, 0.0, 6.0]]
    assert locations["SEALED_PALLETS"]["capacity"] == 8
    placements = [e for e in proposal["events"] if e["kind"] == "cargo_placed"]
    opened = next(e for e in placements if e["payload"]["container_id"] == "OPEN_PALLET")
    assert opened["entity_id"] == "PAL0001"
    assert opened["at_s"] == 124.0  # scan starts at shipping arrival; placement is at132
    assert opened["payload"]["slot_index"] == 0


def test_proposal_blocked_snapshot_links_action(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    inputs = fixture_inputs(bundle, load_fixture(contracts_dir))
    inputs = dataclasses.replace(
        inputs,
        scenario=inputs.scenario.model_copy(update={"horizon_s": 32.9}),
        config=inputs.config.model_copy(update={"max_drain_s": 0, "snapshot_interval_s": 0.1}),
    )
    engine = Engine(inputs, check_invariants=True)
    run = export_proposal(engine, engine.run())
    actor = next(a for a in run["snapshots"][-1]["state"]["actors"] if a["actor_id"] == "P01")
    assert actor["state"] == "BLOCKED"
    assert actor["action"] is not None
    assert actor["action"]["reason"] == "awaiting_conveyor_tick"
    assert actor["blocked_since_tick"] == engine.ctx.ticks(32.8)


def test_proposal_emits_pick_stock_and_actor_transitions(proposal: dict[str, Any]) -> None:
    kinds = {event["kind"] for event in proposal["events"]}
    assert {"picked_last", "stock_transferred", "actor_state_changed"} <= kinds
    picked = next(event for event in proposal["events"] if event["kind"] == "picked_last")
    assert picked["at_s"] == pytest.approx((4 + 8.5) / 1.2 + 2 * 6.15)
    transfers = [
        event
        for event in proposal["events"]
        if event["kind"] == "stock_transferred" and event["at_s"] == 52
    ]
    assert sum(event["payload"]["quantity"] for event in transfers) == 2
    assert {event["payload"]["from"]["kind"] for event in transfers} == {"tote"}
    assert {event["payload"]["to"]["kind"] for event in transfers} == {"pack_wip"}


def test_proposal_rejects_invalid_nested_state(proposal: dict[str, Any]) -> None:
    import copy

    altered = copy.deepcopy(proposal)
    state = altered["snapshots"][0]["state"]
    state["actors"][0]["state"] = "FLYING"
    altered["snapshots"][0]["state_hash"] = sha256_hex(state)
    with pytest.raises(ValueError, match="schema"):
        validate_proposal(altered)


def test_proposal_rejects_unknown_container(proposal: dict[str, Any]) -> None:
    import copy

    altered = copy.deepcopy(proposal)
    move = next(e for e in altered["events"] if e["kind"] == "cell_moved")
    move["payload"]["to"] = "UNKNOWN_PLACE"
    with pytest.raises(ValueError, match="container"):
        validate_proposal(altered)


def test_proposal_preserves_separate_pre_shift_track(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    inputs = fixture_inputs(bundle, load_fixture(contracts_dir))
    track = {
        "calendar": "pre_shift",
        "actor_id": "RELOCATION_01",
        "ticks_per_second": 100,
        "shift_start_s": 0,
        "window_ticks": 0,
        "window_s": 0,
        "actions": [],
        "transfers": [],
    }
    plan = {"relocation": track}
    plan_id = sha256_hex(plan)
    inputs = dataclasses.replace(inputs, relocation_plan={**plan, "plan_id": plan_id})
    engine = Engine(inputs, check_invariants=True)
    run = export_proposal(engine, engine.run())
    assert run["pre_shift"] == track
    assert run["relocation_plan_id"] == run["input_hashes"]["relocation_plan"] == plan_id
    assert "RELOCATION_01" not in {actor["actor_id"] for actor in run["actors"]}
