"""V3 manual wire identity and exact graph bindings are independent from Run 2.0."""

import copy
from dataclasses import replace

import pytest

from app.v3.run_export import build_manual_run, validate_manual_run
from tests.v3.test_run_fixtures import empty_run_inputs


def test_manual_wire_preserves_exact_profile_source_and_augmented_geometry() -> None:
    profile, graph, outcome, document = empty_run_inputs()
    result = build_manual_run(profile, graph, outcome, graph_document=document, end_tick_limit=0)
    assert result["schema_id"] == "qoima.manual-run.v3-proposal"
    assert result["clock"]["ticks_per_second"] == 1_000_000
    assert result["profile"]["actors"][0]["speed_m_s"] == {"numerator": 13, "denominator": 10}
    assert result["graph_document"] == document
    assert result["at_end"]["stock_units"] == [["SKU1", 24]]
    assert result["events"] == []
    assert result["capabilities"]["frontend_adapter"] is False
    validate_manual_run(result)
    result["graph_document"]["walk_graph"]["nodes"][0]["world_pos"][0] = 99
    assert document["walk_graph"]["nodes"][0]["world_pos"] == [1, 0, 1]


def test_manual_wire_refuses_graph_mismatch_and_source_identity_changes_run_id() -> None:
    profile, graph, outcome, document = empty_run_inputs()
    bad = copy.deepcopy(document)
    bad["walk_graph"]["nodes"][0]["world_pos"][0] = 2
    with pytest.raises(ValueError, match="graph"):
        build_manual_run(profile, graph, outcome, graph_document=bad, end_tick_limit=0)
    first = build_manual_run(profile, graph, outcome, graph_document=document, end_tick_limit=0)
    changed = replace(profile, provenance_note="Different declared derivation")
    second = build_manual_run(changed, graph, outcome, graph_document=document, end_tick_limit=0)
    assert first["run_id"] != second["run_id"]


@pytest.mark.parametrize("kind", ["made_up", "job_changed", "worker_changed", "lease_acquired"])
def test_manual_event_requires_real_kind_references_and_typed_payload(kind: str) -> None:
    from app.storage.canonical_json import sha256_hex
    from app.v3.execution_types import ManualEvent
    from app.v3.run_values import record

    profile, graph, outcome, document = empty_run_inputs()
    value = build_manual_run(profile, graph, outcome, graph_document=document, end_tick_limit=0)
    value["events"] = [record(ManualEvent(0, 0, kind, "UNKNOWN", "HU1"))]
    value["snapshots"][0]["through_seq"] = 0
    value["snapshots"][0]["state_hash"] = sha256_hex(value["snapshots"][0]["state"])
    with pytest.raises(ValueError):
        validate_manual_run(value)


@pytest.mark.parametrize("damage", ["layout", "actor_duplicate", "mass", "snapshot_future"])
def test_rehashed_manual_run_rejects_incoherent_profile_and_extra_future_state(damage: str) -> None:
    from app.storage.canonical_json import sha256_hex
    from app.v3.run_export import run_identity

    profile, graph, outcome, document = empty_run_inputs()
    value = build_manual_run(profile, graph, outcome, graph_document=document, end_tick_limit=0)
    if damage == "layout":
        value["profile"]["layout_version"] = "unknown"
    elif damage == "actor_duplicate":
        value["profile"]["actors"].append(copy.deepcopy(value["profile"]["actors"][0]))
        value["initial_state"]["workers"].append(
            copy.deepcopy(value["initial_state"]["workers"][0])
        )
        value["initial_state"]["workers"].sort(key=lambda row: row["actor_id"])
        for key in ("at_horizon", "at_end"):
            value[key] = copy.deepcopy(value["initial_state"])
        value["snapshots"][0]["state"] = copy.deepcopy(value["initial_state"])
        value["snapshots"][0]["state_hash"] = sha256_hex(value["initial_state"])
    elif damage == "mass":
        value["profile"]["handling_units"][0]["gross_mass_kg"]["numerator"] = -1
    else:
        row = copy.deepcopy(value["snapshots"][0])
        row["tick"] = row["state"]["tick"] = 1
        row["state_hash"] = sha256_hex(row["state"])
        value["snapshots"].append(row)
    value["run_id"] = run_identity(value)
    with pytest.raises(ValueError):
        validate_manual_run(value)
