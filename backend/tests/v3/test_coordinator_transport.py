"""C bundle publication is manifest-last and strict reads recheck native semantics."""

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.coordinator_run import build_coordinator_run
from app.v3.coordinator_run_inputs import freeze_hand_inputs
from app.v3.coordinator_transport import read_coordinator_run, write_coordinator_run
from tests.v3.test_coordinator_metrics import role_case
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor


def bundle(tmp_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    profile, outcome = role_case(200 * SECOND)
    inputs = freeze_hand_inputs(profile, receipt_conveyor(), 200 * SECOND, 200 * SECOND)
    run = build_coordinator_run(inputs, outcome)
    manifest = write_coordinator_run(run, tmp_path, inputs=inputs.frozen_bytes)
    return run, manifest


def test_bundle_roundtrip_keeps_native_capture_roles_and_halfopen_event_chunks(
    tmp_path: Path,
) -> None:
    run, manifest = bundle(tmp_path)
    assert read_coordinator_run(tmp_path) == run
    assert manifest["transport_version"] == "qoima-coordinator-run-bundle-0.1.0"
    assert manifest["inputs"]["path"] == "inputs.json"
    for ref in manifest["event_chunks"]:
        rows = parse_json((tmp_path / ref["path"]).read_bytes())
        assert all(ref["start_tick"] <= row["tick"] < ref["end_tick"] for row in rows)
    terminal = next(ref for ref in manifest["snapshot_chunks"] if "at_end" in ref["roles"])
    assert terminal["tick"] == 200 * SECOND
    assert set(terminal["roles"]) == {"at_horizon", "at_end", "checkpoint"}


def test_writer_allows_only_exact_preexisting_frozen_inputs(tmp_path: Path) -> None:
    profile, outcome = role_case(200 * SECOND)
    inputs = freeze_hand_inputs(profile, receipt_conveyor(), 200 * SECOND, 200 * SECOND)
    run = build_coordinator_run(inputs, outcome)
    (tmp_path / "inputs.json").write_bytes(inputs.frozen_bytes)
    write_coordinator_run(run, tmp_path, inputs=inputs.frozen_bytes)
    with pytest.raises(ValueError):
        write_coordinator_run(run, tmp_path, inputs=inputs.frozen_bytes)


def test_reader_rejects_rehashed_missing_cart_in_exact_captured_state(tmp_path: Path) -> None:
    _, manifest = bundle(tmp_path)
    ref = next(r for r in manifest["snapshot_chunks"] if "at_end" in r["roles"])
    state = parse_json((tmp_path / ref["path"]).read_bytes())
    state["carts"] = []
    raw = canonical_bytes(state)
    (tmp_path / ref["path"]).write_bytes(raw)
    ref.update(bytes=len(raw), sha256=sha256(raw).hexdigest())
    (tmp_path / "manifest.json").write_bytes(canonical_bytes(manifest))
    with pytest.raises(ValueError):
        read_coordinator_run(tmp_path)


def test_reader_rejects_extra_files_and_manifest_path_escape(tmp_path: Path) -> None:
    _, manifest = bundle(tmp_path)
    (tmp_path / "extra.json").write_bytes(b"{}")
    with pytest.raises(ValueError):
        read_coordinator_run(tmp_path)
    (tmp_path / "extra.json").unlink()
    wrong = deepcopy(manifest)
    wrong["inputs"]["path"] = "../inputs.json"
    (tmp_path / "manifest.json").write_bytes(canonical_bytes(wrong))
    with pytest.raises(ValueError):
        read_coordinator_run(tmp_path)
