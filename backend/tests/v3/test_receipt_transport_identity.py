"""Input order is nonsemantic; declared process provenance and actual T60 boundary are bound."""

from dataclasses import replace
from pathlib import Path

from app.storage.canonical_json import canonical_bytes, parse_json, sha256_hex
from app.v3.receipt_run import build_receipt_run
from app.v3.receipt_transport import event_window, write_receipt_run
from tests.v3.test_receipt_run_fixtures import sample


def test_canonical_object_permutation_preserves_every_artifact_byte(tmp_path: Path) -> None:
    inputs, outcome = sample()
    frozen = parse_json(inputs.frozen_bytes)
    reordered = canonical_bytes(dict(reversed(list(frozen.items()))))
    again = replace(inputs, frozen_bytes=reordered)
    first, second = build_receipt_run(inputs, outcome), build_receipt_run(again, outcome)
    assert first["run_id"] == second["run_id"]
    for name, run in (("a", first), ("b", second)):
        write_receipt_run(run, tmp_path / name, inputs=reordered)
    a, b = tmp_path / "a", tmp_path / "b"
    assert {p.relative_to(a): p.read_bytes() for p in a.rglob("*.json")} == {
        p.relative_to(b): p.read_bytes() for p in b.rglob("*.json")
    }


def test_changed_declared_provenance_changes_native_identity() -> None:
    inputs, outcome = sample()
    original = build_receipt_run(inputs, outcome)
    profile = replace(inputs.profile, flow=replace(inputs.profile.flow, provenance="second recipe"))
    frozen = parse_json(inputs.frozen_bytes)
    frozen["profile"]["provenance"] = profile.flow.provenance
    changed = replace(
        inputs, profile=profile, frozen_bytes=canonical_bytes(frozen), input_hash=sha256_hex(frozen)
    )
    other = build_receipt_run(changed, outcome)
    assert original["run_id"] != other["run_id"]
    assert original["events"] == other["events"]


def test_exact_t60_arrival_belongs_to_second_chunk_and_settled_checkpoint(tmp_path: Path) -> None:
    inputs, outcome = sample(arrival=60_000_000)
    run = build_receipt_run(inputs, outcome)
    manifest = write_receipt_run(run, tmp_path, inputs=inputs.frozen_bytes)
    before = event_window(tmp_path, 0, 60_000_000)
    after = event_window(tmp_path, 60_000_000, 120_000_000)
    assert not any(e["kind"] == "receipt_arrived" for e in before)
    arrival = next(e for e in after if e["kind"] == "receipt_arrived")
    assert arrival["tick"] == 60_000_000
    point = next(c for c in run["checkpoints"] if c["tick"] == 60_000_000)
    assert point["last_seq"] >= arrival["seq"]
    assert point["state"]["receipts"][0]["admitted_tick"] == 60_000_000
    assert len(point["state"]["stock"]["locations"]) == 24
    assert any(c["start_tick"] == 60_000_000 for c in manifest["event_chunks"])
