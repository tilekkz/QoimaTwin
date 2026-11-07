"""Contract projection and identity, checked with hand-derived fixture milestones."""

import copy
import dataclasses
import hashlib
import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from app.contracts.loader import ContractBundle
from app.exporter.events import project_events
from app.exporter.identity import fingerprint
from app.exporter.run import export_run, write_run
from app.exporter.validation import validate_run
from app.simulation.engine import Engine
from app.simulation.fixtures import fixture_inputs, load_fixture
from app.storage.canonical_json import canonical_bytes, sha256_hex


@pytest.fixture(scope="module")
def exported(bundle: ContractBundle, contracts_dir: Path) -> dict[str, Any]:
    engine = Engine(fixture_inputs(bundle, load_fixture(contracts_dir)), check_invariants=True)
    return export_run(engine, engine.run())


def test_inline_matches_v2_schema(exported: dict[str, Any], contracts_dir: Path) -> None:
    schema = json.loads((contracts_dir / "run.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(exported)
    assert len(exported["actors"]) == 24
    assert exported["metrics"]["dispatched_total"] == 1


def test_transfer_pairs_and_sequence(exported: dict[str, Any]) -> None:
    events = exported["events"]
    assert [e["seq"] for e in events] == list(range(len(events)))
    assert [(e["at_s"], e["phase"]) for e in events] == sorted(
        (e["at_s"], e["phase"]) for e in events
    )
    pairs: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        if event["kind"].startswith("cell_"):
            pairs.setdefault(event["payload"]["transition_id"], []).append(event)
    assert len(pairs) == 68  # 19+47 traversals plus two admissions, from the fixture.
    for exited, entered in pairs.values():
        assert exited["kind"] == "cell_exited"
        assert entered["kind"] == "cell_entered"
        assert entered["seq"] == exited["seq"] + 1
        assert entered["at_s"] == exited["at_s"]
        assert entered["payload"]["cargo_id"] == exited["payload"]["cargo_id"]


def test_transfer_precedes_acceptance_event(exported: dict[str, Any]) -> None:
    events = exported["events"]
    inducted = next(e for e in events if e["kind"] == "tote_inducted")
    entered = events[inducted["seq"] - 1]
    assert entered["kind"] == "cell_entered"
    assert entered["at_s"] == 33
    assert entered["payload"]["cell_id"] == inducted["payload"]["cell_id"]


def test_identity_stock_is_assignment_independent(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    inputs = fixture_inputs(bundle, load_fixture(contracts_dir))
    first = fingerprint(inputs)
    lots = list(inputs.assignment.initial_lots)
    a, b = lots[:2]
    lots[:2] = [
        a.model_copy(update={"slot_id": b.slot_id}),
        b.model_copy(update={"slot_id": a.slot_id}),
    ]
    changed = dataclasses.replace(
        inputs, assignment=inputs.assignment.model_copy(update={"initial_lots": tuple(lots)})
    )
    second = fingerprint(changed)
    assert first["hashes"]["initial_inventory"] == second["hashes"]["initial_inventory"]
    assert first["hashes"]["assignment"] != second["hashes"]["assignment"]
    assert sha256_hex(first) != sha256_hex(second)
    assert fingerprint(inputs, engine_version="other") != first


def test_identity_includes_empty_scenario_horizon(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    inputs = fixture_inputs(bundle, load_fixture(contracts_dir))
    changed = dataclasses.replace(
        inputs, scenario=inputs.scenario.model_copy(update={"horizon_s": 100.0})
    )
    assert fingerprint(inputs) != fingerprint(changed)


def test_identity_normalizes_actor_set_order(bundle: ContractBundle, contracts_dir: Path) -> None:
    inputs = fixture_inputs(bundle, load_fixture(contracts_dir))
    changed = dataclasses.replace(
        inputs,
        actors=inputs.actors.model_copy(update={"actors": tuple(reversed(inputs.actors.actors))}),
    )
    assert fingerprint(inputs) == fingerprint(changed)


def test_equal_identity_reordered_lines_has_equal_events(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    inputs = fixture_inputs(bundle, load_fixture(contracts_dir))
    order = inputs.scenario.orders[0]
    reordered = order.model_copy(update={"lines": tuple(reversed(order.lines))})
    changed = dataclasses.replace(
        inputs, scenario=inputs.scenario.model_copy(update={"orders": (reordered,)})
    )
    engines = [Engine(value, check_invariants=True) for value in (inputs, changed)]
    for engine in engines:
        engine.run()
    assert fingerprint(inputs) == fingerprint(changed)
    assert project_events(engines[0]) == project_events(engines[1])


def test_bundle_roundtrip_and_hashes(exported: dict[str, Any], tmp_path: Path) -> None:
    manifest = write_run(exported, tmp_path)
    restored_events = []
    actions = {}
    snapshots = []

    for chunk in manifest["chunks"]:
        raw = (tmp_path / chunk["path"]).read_bytes()
        assert len(raw) == chunk["bytes"]
        assert hashlib.sha256(raw).hexdigest() == chunk["sha256"]
        payload = json.loads(raw)
        restored_events.extend(payload["events"])
        actions.update({a["action_id"]: a for a in payload["actions"]})
        snapshots.extend(payload["snapshots"])
        assert all(chunk["start_s"] <= e["at_s"] < chunk["end_s"] for e in payload["events"])
    assert restored_events == exported["events"]
    assert (tmp_path / "run.json").read_bytes() == canonical_bytes(exported)
    catalog = json.loads((tmp_path / manifest["catalog"]["path"]).read_bytes())
    assert {
        **catalog,
        "events": restored_events,
        "snapshots": snapshots,
        "actions": sorted(actions.values(), key=lambda a: (a["start_s"], a["action_id"])),
    } == exported


@pytest.mark.parametrize("damage", ["missing_payload", "orphan", "transition", "geometry"])
def test_semantic_validator_rejects_corruption(exported: dict[str, Any], damage: str) -> None:
    bad = copy.deepcopy(exported)
    if damage == "missing_payload":
        bad["events"][0]["payload"] = {}
    elif damage in ("orphan", "transition"):
        entered = next(e for e in bad["events"] if e["kind"] == "cell_entered")
        if damage == "orphan":
            bad["events"].remove(entered)
        else:
            entered["payload"]["transition_id"] = "wrong"
    else:
        bad["actions"][0]["pos"] = [0, 0, 0]
    with pytest.raises(ValueError):
        validate_run(bad)


def test_cutoff_exports_only_executed_action_portions(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    inputs = fixture_inputs(bundle, load_fixture(contracts_dir))
    inputs = dataclasses.replace(
        inputs,
        scenario=inputs.scenario.model_copy(update={"horizon_s": 10.0}),
        config=inputs.config.model_copy(update={"max_drain_s": 0}),
    )
    engine = Engine(inputs, check_invariants=True)
    run = export_run(engine, engine.run())
    assert max(a["end_s"] for a in run["actions"]) == 10
    assert all(a["start_s"] < 10 for a in run["actions"])
    assert run["metrics"]["dispatched_total"] == 0


def test_open_pallet_has_catalog_identity(bundle: ContractBundle, contracts_dir: Path) -> None:
    inputs = fixture_inputs(bundle, load_fixture(contracts_dir))
    inputs = dataclasses.replace(
        inputs,
        scenario=inputs.scenario.model_copy(update={"horizon_s": 200.0}),
        config=inputs.config.model_copy(update={"max_drain_s": 0}),
    )
    engine = Engine(inputs, check_invariants=True)
    run = export_run(engine, engine.run())
    scanned = next(e for e in run["events"] if e["kind"] == "parcel_scanned")
    assert scanned["payload"]["pallet_id"] in {c["cargo_id"] for c in run["cargo"]}


@pytest.mark.parametrize("seconds,actor,start", [(32.9, "P01", 32.8), (76.5, "K01", 76.1)])
def test_cutoff_keeps_open_block(
    bundle: ContractBundle, contracts_dir: Path, seconds: float, actor: str, start: float
) -> None:
    inputs = fixture_inputs(bundle, load_fixture(contracts_dir))
    inputs = dataclasses.replace(
        inputs,
        scenario=inputs.scenario.model_copy(update={"horizon_s": seconds}),
        config=inputs.config.model_copy(update={"max_drain_s": 0}),
    )
    engine = Engine(inputs, check_invariants=True)
    run = export_run(engine, engine.run())
    blocks = [a for a in run["actions"] if a["actor_id"] == actor and a["state"] == "BLOCKED"]
    assert blocks[-1]["start_s"] == start
    assert blocks[-1]["end_s"] == seconds


def test_manifest_rejects_metadata_override(exported: dict[str, Any], tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="authoritative"):
        write_run(exported, tmp_path, metadata={"run_id": "wrong", "chunks": []})
    assert not (tmp_path / "run.json").exists()


def test_metrics_export_uses_one_coherent_horizon_window(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    inputs = fixture_inputs(bundle, load_fixture(contracts_dir))
    inputs = dataclasses.replace(
        inputs, scenario=inputs.scenario.model_copy(update={"horizon_s": 10.0})
    )
    engine = Engine(inputs, check_invariants=True)
    metrics = export_run(engine, engine.run())["metrics"]
    assert metrics["backlog_at_horizon"] == 1
    assert metrics["dispatched_total"] == 0
    assert metrics["mean_cycle_s"] is None
    assert metrics["p95_cycle_s"] is None
    assert metrics["role_metrics"]["picker"]["active"] == 1 / 12
    assert metrics["queue_metrics"]["orders"] == 0


def test_chunk_supplies_actions_for_seek(exported: dict[str, Any], tmp_path: Path) -> None:
    manifest = write_run(exported, tmp_path)
    for time, actor, operation in [(5, "P01", "pick"), (455, "F02", "loading")]:
        chunk = next(c for c in manifest["chunks"] if c["start_s"] <= time < c["end_s"])
        payload = json.loads((tmp_path / chunk["path"]).read_text(encoding="utf-8"))
        active = [
            a
            for a in payload["actions"]
            if a["actor_id"] == actor and a["start_s"] <= time < a["end_s"]
        ]
        assert len(active) == 1
        assert active[0]["operation"] == operation


@pytest.mark.parametrize("cutoff", [31.0, 450.0])
def test_partial_snapshot_actions_match_export_cutoff(
    bundle: ContractBundle, contracts_dir: Path, cutoff: float
) -> None:
    inputs = fixture_inputs(bundle, load_fixture(contracts_dir))
    inputs = dataclasses.replace(
        inputs,
        scenario=inputs.scenario.model_copy(update={"horizon_s": cutoff}),
        config=inputs.config.model_copy(update={"max_drain_s": 0}),
    )
    engine = Engine(inputs, check_invariants=True)
    run = export_run(engine, engine.run())
    actions = {a["action_id"]: a for a in run["actions"]}
    for snapshot in run["snapshots"]:
        for actor in snapshot["state"]["actors"]:
            action = actor["action"]
            if action is not None:
                assert action["action_id"] in actions
                assert action["end_tick"] / 3_000_000 == actions[action["action_id"]]["end_s"]
        state = dict(snapshot["state"])
        metadata = state.pop("checkpoint")
        assert metadata["state_hash"] == sha256_hex(state)
