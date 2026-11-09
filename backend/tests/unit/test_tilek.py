"""Visual projection regression oracles, independent of the frontend renderer."""

import copy
import dataclasses
import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from app.contracts.loader import ContractBundle
from app.exporter.identity import fingerprint
from app.exporter.run import export_run
from app.exporter.tilek import WIRE_VERSION, write_tilek_run
from app.exporter.tilek import export_tilek_run as candidate
from app.exporter.tilek_validation import validate_tilek_run
from app.simulation.engine import Engine, RunOutcome
from app.simulation.fixtures import fixture_inputs, load_fixture
from app.storage.canonical_json import canonical_bytes, sha256_hex
from tests.builders import fixture_order, receipt, run_inputs, scenario, simulate


@pytest.mark.parametrize("publication", ["export", "writer"])
def test_one_schema_validation_per_visual_publication(
    analytical_run: tuple[Engine, RunOutcome],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    publication: str,
) -> None:
    run = candidate(*analytical_run, validate=False)
    calls: list[object] = []
    original = jsonschema.Draft202012Validator.validate

    def spy(self: Any, instance: Any, *args: Any, **kwargs: Any) -> None:
        calls.append(instance)
        original(self, instance, *args, **kwargs)

    monkeypatch.setattr(jsonschema.Draft202012Validator, "validate", spy)
    if publication == "export":
        candidate(*analytical_run)
    else:
        write_tilek_run(run, tmp_path)
    assert len(calls) == 1


@pytest.mark.parametrize("target", ["source", "visual"])
@pytest.mark.parametrize("damage", ["pair", "payload", "quantity"])
def test_source_semantics_remain_mandatory(
    analytical_run: tuple[Engine, RunOutcome],
    target: str,
    damage: str,
) -> None:
    from app.exporter.validation import validate_run

    run = (candidate if target == "visual" else export_run)(*analytical_run, validate=False)
    if damage == "pair":
        event = next(e for e in run["events"] if e["kind"] == "cell_entered")
        event["payload"]["transition_id"] = "wrong-pair"
        message = "mismatched transfer pair"
    else:
        event = next(e for e in run["events"] if e["kind"] == "sku_picked")
        if damage == "payload":
            event["payload"].pop("lot_id")
            message = "missing payload fields"
        else:
            event["payload"]["quantity"] = 0
            message = "quantity must be positive"
    with pytest.raises(ValueError, match=message):
        (validate_tilek_run if target == "visual" else validate_run)(run)


@pytest.fixture(scope="module")
def visual(analytical_run: tuple[Engine, RunOutcome]) -> dict[str, Any]:
    return candidate(*analytical_run)


def test_scanned_pallet_has_physical_location(visual: dict[str, Any]) -> None:
    scan = next(e for e in visual["events"] if e["kind"] == "parcel_scanned")
    assert scan["payload"].get("pos") == [64.92, 0.0, 6.0]


def test_forklift_service_and_empty_trip(visual: dict[str, Any]) -> None:
    actions = [a for a in visual["actions"] if a["actor_id"] == "F02"]
    assert [(a["operation"], a["entity_id"]) for a in actions] == [
        ("drive", None),
        ("loading", "PAL0001"),
        ("drive", "PAL0001"),
        ("unloading", "PAL0001"),
        ("drive", None),
    ]


def test_schema_identity_and_source_immutable(
    analytical_run: tuple[Engine, RunOutcome], visual: dict[str, Any], contracts_dir: Path
) -> None:
    engine, _ = analytical_run
    before = canonical_bytes(export_run(*analytical_run))
    journal = copy.deepcopy(engine.ctx.recorder)
    assert candidate(*analytical_run) == visual
    assert canonical_bytes(export_run(*analytical_run)) == before
    assert engine.ctx.recorder == journal
    source = json.loads(before)
    assert visual["run_id"] != source["run_id"]
    assert visual["run_id"] == sha256_hex(
        {**fingerprint(engine.ctx.inputs), "wire_version": WIRE_VERSION}
    )
    for field in ("metrics", "cargo", "initial_state", "actors", "horizon_s", "input_hashes"):
        assert visual[field] == source[field]
    schema = json.loads((contracts_dir / "run.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(visual)
    binding = visual["events"][0]["payload"]["visual_projection"]
    assert binding["wire_version"] == "tilek-visual-v1"
    assert binding["source_run_id"] == source["run_id"]
    assert binding["visual_projection_limitations"]


def test_all_source_events_and_actions_retained(
    analytical_run: tuple[Engine, RunOutcome], visual: dict[str, Any]
) -> None:
    source = export_run(*analytical_run)
    bound = [e for e in visual["events"] if "source_seq" in e["payload"]]
    assert len(bound) == len(source["events"])
    for old, new in zip(source["events"], bound, strict=True):
        assert new["payload"]["source_seq"] == old["seq"]
        for key in ("at_s", "phase", "kind", "entity_id"):
            assert new[key] == old[key]
        assert new["payload"].items() >= old["payload"].items()
    assert [a["action_id"] for a in visual["actions"]] == [
        a["action_id"] for a in source["actions"]
    ]
    assert [(a["start_s"], a["end_s"]) for a in visual["actions"]] == [
        (a["start_s"], a["end_s"]) for a in source["actions"]
    ]
    old_cells = [e for e in source["events"] if e["kind"].startswith("cell_")]
    new_cells = [e for e in bound if e["kind"].startswith("cell_")]
    assert len(new_cells) == len(old_cells) == 136
    assert {e["payload"]["cell_id"] for e in new_cells} >= {"PK01", "SHIPPING", "inlet"}


def test_manual_outbound_timing_and_handoffs(visual: dict[str, Any]) -> None:
    events = visual["events"]
    expected = {
        "handoff_ready": 32.8,
        "tote_inducted": 33,
        "pack_started": 52,
        "order_packed": 76.1,
        "parcel_outfed": 77,
        "shipping_arrived": 124,
        "parcel_scanned": 132,
        "pallet_sealed": 432,
        "order_dispatched": 469,
    }
    for kind, seconds in expected.items():
        assert next(e["at_s"] for e in events if e["kind"] == kind) == seconds
    pickup, drop = [
        e
        for e in events
        if e["payload"].get("physical_event") in {"cargo_attached", "cargo_detached"}
    ]
    assert pickup["at_s"] == 450  # 432 + 6/2 empty travel + 15 pickup
    assert drop["at_s"] == 469  # 450 + 8/2 loaded travel + 15 drop
    assert pickup["payload"]["actor_id"] == "F02"
    assert pickup["payload"]["state"] == "TRAVEL"
    assert pickup["payload"]["attachment"]["kind"] == "vehicle"
    assert drop["payload"]["attachment"] == {"kind": "world"}
    assert drop["seq"] < next(e["seq"] for e in events if e["kind"] == "order_dispatched")
    assert max(a["end_s"] for a in visual["actions"]) == 474


def test_receiving_placement_and_handoff_oracle(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    engine, outcome = simulate(run_inputs(bundle, contracts_dir, scenario([], [receipt(0)])))
    run = candidate(engine, outcome)
    accepted = next(e for e in run["events"] if e["kind"] == "receipt_accepted")
    assert accepted["at_s"] == 90
    assert accepted["payload"]["pos"] == [4.0, 0.0, 36.92]
    handoffs = [
        e
        for e in run["events"]
        if e["payload"].get("physical_event") in {"cargo_attached", "cargo_detached"}
    ]
    assert [e["at_s"] for e in handoffs] == [198, 224]
    stored = next(e for e in run["events"] if e["kind"] == "pallet_putaway")
    assert stored["payload"]["pos"] == [4.0, 0.0, 14.92]
    assert stored["payload"]["attachment"] == {"kind": "world"}
    assert max(a["end_s"] for a in run["actions"]) == 238
    assert engine.ctx.ledger.check_conservation() == []


@pytest.mark.parametrize(
    "cutoff,attached", [(32.9, False), (449.0, False), (450.0, True), (460.0, True)]
)
def test_cutoff_has_no_fake_completion(
    bundle: ContractBundle, contracts_dir: Path, cutoff: float, attached: bool
) -> None:
    inputs = fixture_inputs(bundle, load_fixture(contracts_dir))
    inputs = dataclasses.replace(
        inputs,
        scenario=inputs.scenario.model_copy(update={"horizon_s": cutoff}),
        config=inputs.config.model_copy(update={"max_drain_s": 0}),
    )
    engine = Engine(inputs, check_invariants=True)
    outcome = engine.run()
    run = candidate(engine, outcome)
    assert all(a["start_s"] < a["end_s"] <= cutoff for a in run["actions"])
    assert all(e["at_s"] <= cutoff for e in run["events"])
    assert not any(e["kind"] == "order_dispatched" for e in run["events"])
    handoffs = [e for e in run["events"] if e["payload"].get("physical_event") == "cargo_attached"]
    assert bool(handoffs) is attached
    assert not any(e["payload"].get("physical_event") == "cargo_detached" for e in run["events"])


def test_snapshots_keep_source_state_and_bind_new_sequence(
    analytical_run: tuple[Engine, RunOutcome], visual: dict[str, Any]
) -> None:
    for old, new in zip(export_run(*analytical_run)["snapshots"], visual["snapshots"], strict=True):
        state = copy.deepcopy(new["state"])
        checkpoint = state.pop("checkpoint")
        assert checkpoint["state_hash"] == sha256_hex(state)
        assert state.pop("source_checkpoint") == old["state"]["checkpoint"]
        state.pop("visual_projection")
        assert state == {k: v for k, v in old["state"].items() if k != "checkpoint"}
        assert checkpoint["last_seq"] == max(
            e["seq"] for e in visual["events"] if e["at_s"] <= new["at_s"]
        )


def test_writer_and_chunks(visual: dict[str, Any], tmp_path: Path) -> None:
    manifest = write_tilek_run(visual, tmp_path)
    assert json.loads((tmp_path / "run.json").read_bytes()) == visual
    assert manifest["provenance"]["wire_version"] == WIRE_VERSION
    assert manifest["provenance"]["source_run_id"] != visual["run_id"]
    events = [
        e
        for c in manifest["chunks"]
        for e in json.loads((tmp_path / c["path"]).read_bytes())["events"]
    ]
    assert events == visual["events"]


def test_writer_rejects_override(visual: dict[str, Any], tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="authoritative"):
        write_tilek_run(visual, tmp_path, metadata={"run_id": "wrong"})
    assert not (tmp_path / "run.json").exists()


def test_visual_validator_rejects_bad_transition(visual: dict[str, Any]) -> None:
    damaged = copy.deepcopy(visual)
    damaged["events"][0]["payload"].pop("actor_id")
    with pytest.raises(ValueError, match="binding"):
        validate_tilek_run(damaged)


def test_writer_rejects_source_run(
    analytical_run: tuple[Engine, RunOutcome], tmp_path: Path
) -> None:
    with pytest.raises(ValueError, match="binding"):
        write_tilek_run(export_run(*analytical_run), tmp_path)
    assert not (tmp_path / "run.json").exists()


def test_scan_start_is_bound_to_real_actor_and_pallet(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    inputs = run_inputs(
        bundle,
        contracts_dir,
        scenario([fixture_order(0, f"O{i}") for i in range(4)]),
        parcels_per_pallet=1,
    )
    engine, outcome = simulate(inputs)
    run = candidate(engine, outcome)
    placed = [e for e in run["events"] if e["payload"].get("transition") == "scan_started"]
    assert len(placed) == 4
    actions = {a.action_id: a for a in engine.ctx.recorder.actions}
    scanned = {e.entity_id: e.payload for e in engine.ctx.recorder.of_kind("parcel_scanned")}
    for event in placed:
        payload = event["payload"]
        action = actions[payload["action_id"]]
        assert action.actor_id == payload["actor_id"] == event["entity_id"]
        assert action.start_tick == payload["at_tick"]
        assert scanned[action.entity_id or ""]["pallet_id"] == payload["cargo_id"]
