"""Actual hand runs exercise N1 transport boundaries without any source DES."""

from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.relocation_engine import RelocationEngine
from app.v3.relocation_run import build_relocation_run
from app.v3.relocation_run_inputs import freeze_hand_inputs
from app.v3.relocation_transport import read_relocation_run, write_relocation_run
from tests.v3.test_receipt_flow_fixtures import receipt_conveyor
from tests.v3.test_relocation_runtime_fixtures import SECOND, relocation_hand


def hand_run(*, end: int = 80 * SECOND, noop: bool = False) -> tuple[dict[str, Any], bytes]:
    profile = relocation_hand()
    jobs = () if noop else (replace(profile.jobs[0], arrival_tick=60 * SECOND),)
    profile = replace(profile, jobs=jobs)
    conveyor, horizon = receipt_conveyor(), 61 * SECOND
    inputs = freeze_hand_inputs(profile, conveyor, horizon, end)
    outcome = RelocationEngine(profile, conveyor).run(horizon, end)
    return build_relocation_run(inputs, outcome), inputs.frozen_bytes


@pytest.fixture(scope="module")
def complete() -> tuple[dict[str, Any], bytes]:
    return hand_run()


def change_file(root: Path, manifest: dict[str, Any], ref: dict[str, Any], value: object) -> None:
    raw = canonical_bytes(value)
    (root / ref["path"]).write_bytes(raw)
    ref.update(bytes=len(raw), sha256=sha256(raw).hexdigest())
    (root / "manifest.json").write_bytes(canonical_bytes(manifest))


def test_tick60_events_use_the_next_chunk_and_checkpoint_is_fully_settled(
    tmp_path: Path, complete: tuple[dict[str, Any], bytes]
) -> None:
    run, inputs = complete
    manifest = write_relocation_run(run, tmp_path, inputs=inputs)
    assert read_relocation_run(tmp_path) == run
    assert manifest["transport_version"] == "qoima-relocation-run-bundle-0.1.0"
    assert manifest["common_input_hash"] == run["common_input_hash"]
    ref = next(r for r in manifest["event_chunks"] if r["start_tick"] == 60 * SECOND)
    rows = parse_json((tmp_path / ref["path"]).read_bytes())
    assert ref["end_tick"] == 120 * SECOND
    assert any(r["tick"] == 60 * SECOND and r["kind"] == "relocation_admitted" for r in rows)
    assert all(60 * SECOND <= r["tick"] < 120 * SECOND for r in rows)
    point_ref = next(r for r in manifest["snapshot_chunks"] if r["tick"] == 60 * SECOND)
    point = parse_json((tmp_path / point_ref["path"]).read_bytes())
    assert point_ref["roles"] == ["checkpoint"]
    assert point["last_seq"] == max(
        e["seq"] for e in run["outcome"]["events"] if e["tick"] <= 60 * SECOND
    )
    assert point["relocations"][0]["status"] == "approaching"
    assert point["relocations"][0]["admitted_tick"] == 60 * SECOND
    assert point["relocations"][0]["taken_tick"] is None
    final = run["outcome"]["at_end"]["relocations"][0]
    assert (final["taken_tick"], final["placed_tick"], final["returned_tick"]) == (
        64 * SECOND,
        68 * SECOND,
        73 * SECOND,
    )


@pytest.mark.parametrize(
    "noop,end,status", [(False, 65 * SECOND, "partial"), (True, 80 * SECOND, "complete")]
)
def test_partial_and_base_noop_roundtrip_preserve_native_scope(
    tmp_path: Path, noop: bool, end: int, status: str
) -> None:
    run, inputs = hand_run(end=end, noop=noop)
    manifest = write_relocation_run(run, tmp_path, inputs=inputs)
    restored = read_relocation_run(tmp_path)
    assert restored == run and restored["status"] == status
    assert restored["outcome_kind"] == ("base_noop" if noop else "relocation")
    terminal = next(r for r in manifest["snapshot_chunks"] if "at_end" in r["roles"])
    assert terminal["tick"] == (61 * SECOND if noop else end)


def test_rehashed_native_return_cannot_forge_a_completed_operation(
    tmp_path: Path, complete: tuple[dict[str, Any], bytes]
) -> None:
    run, inputs = complete
    manifest = write_relocation_run(run, tmp_path, inputs=inputs)
    ref = next(r for r in manifest["snapshot_chunks"] if "at_end" in r["roles"])
    point = parse_json((tmp_path / ref["path"]).read_bytes())
    point["relocations"][0]["returned_tick"] = 72 * SECOND
    change_file(tmp_path, manifest, ref, point)
    with pytest.raises(ValueError):
        read_relocation_run(tmp_path)


def test_rehashed_event_cannot_cross_its_declared_halfopen_chunk(
    tmp_path: Path, complete: tuple[dict[str, Any], bytes]
) -> None:
    run, inputs = complete
    manifest = write_relocation_run(run, tmp_path, inputs=inputs)
    ref = next(r for r in manifest["event_chunks"] if r["start_tick"] == 60 * SECOND)
    rows = parse_json((tmp_path / ref["path"]).read_bytes())
    rows[0]["tick"] = 59 * SECOND
    change_file(tmp_path, manifest, ref, rows)
    with pytest.raises(ValueError, match="half-open"):
        read_relocation_run(tmp_path)


@pytest.mark.parametrize(
    "field", ["transport_version", "schema_version", "engine_version", "common_input_hash"]
)
def test_manifest_identity_cannot_relabel_the_native_run(
    tmp_path: Path, complete: tuple[dict[str, Any], bytes], field: str
) -> None:
    run, inputs = complete
    manifest = write_relocation_run(run, tmp_path, inputs=inputs)
    manifest[field] = "0" * 64 if field == "common_input_hash" else "qoima-coordinator-run-0.1.0"
    (tmp_path / "manifest.json").write_bytes(canonical_bytes(manifest))
    with pytest.raises(ValueError):
        read_relocation_run(tmp_path)


@pytest.mark.parametrize("path", ["../inputs.json", "inputs.json", "C:/catalog.json"])
def test_paths_cannot_escape_or_alias_other_file_roles(
    tmp_path: Path, complete: tuple[dict[str, Any], bytes], path: str
) -> None:
    run, inputs = complete
    manifest = write_relocation_run(run, tmp_path, inputs=inputs)
    manifest["catalog"]["path"] = path
    (tmp_path / "manifest.json").write_bytes(canonical_bytes(manifest))
    with pytest.raises(ValueError):
        read_relocation_run(tmp_path)


@pytest.mark.parametrize("change", ["extra", "truncate", "manifest_whitespace", "unknown_field"])
def test_closed_inventory_raw_bounds_and_canonical_manifest_are_enforced(
    tmp_path: Path, complete: tuple[dict[str, Any], bytes], change: str
) -> None:
    run, inputs = complete
    manifest = write_relocation_run(run, tmp_path, inputs=inputs)
    if change == "extra":
        (tmp_path / "extra.json").write_bytes(b"{}")
    elif change == "truncate":
        path = tmp_path / "catalog.json"
        path.write_bytes(path.read_bytes()[:-1])
    elif change == "manifest_whitespace":
        path = tmp_path / "manifest.json"
        path.write_bytes(path.read_bytes() + b"\n")
    else:
        manifest["ignored"] = 0
        (tmp_path / "manifest.json").write_bytes(canonical_bytes(manifest))
    with pytest.raises(ValueError):
        read_relocation_run(tmp_path)


def test_repeat_publication_preserves_every_existing_byte(
    tmp_path: Path, complete: tuple[dict[str, Any], bytes]
) -> None:
    run, inputs = complete
    (tmp_path / "inputs.json").write_bytes(inputs)
    write_relocation_run(run, tmp_path, inputs=inputs)
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    with pytest.raises(ValueError):
        write_relocation_run(run, tmp_path, inputs=inputs)
    assert before == {
        p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()
    }


def test_writer_rejects_disagreeing_same_tick_roles_before_publication(tmp_path: Path) -> None:
    run, inputs = hand_run(noop=True)
    forged = deepcopy(run)
    assert forged["outcome"]["at_horizon"]["tick"] == forged["outcome"]["at_end"]["tick"]
    forged["outcome"]["at_end"]["last_seq"] += 1
    output = tmp_path / "never-published"
    with pytest.raises(ValueError):
        write_relocation_run(forged, output, inputs=inputs)
    assert not output.exists()
