"""Chunk boundaries, content hashes, compact checkpoint chains and atomic cell replay."""

import hashlib
import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from app.contracts.loader import ContractBundle
from app.data.scenario_materializer import _atomic_write
from app.exporter.proposal import write_proposal_run
from app.exporter.wire_checkpoint_codec import decode_snapshot, encode_snapshots
from app.exporter.wire_schema import validate_proposal
from app.simulation.chunks import split_events
from app.simulation.fixtures import fixture_inputs, load_fixture
from tests.unit.test_proposal_export import proposal as proposal


def test_snapshot_balance_deltas_reconstruct_full_state(proposal: dict[str, Any]) -> None:
    encoded = list(encode_snapshots(proposal["snapshots"], full_every=3))
    assert encoded[0]["encoding"] == "full"
    assert encoded[1]["encoding"] == "delta"
    assert encoded[3]["encoding"] == "full"
    assert "balances" not in encoded[1]["state"]["ledger"]
    previous = None
    for compact, original in zip(encoded, proposal["snapshots"], strict=True):
        decoded = decode_snapshot(compact, previous)
        assert decoded == original
        previous = decoded


def test_stream_bundle_has_raw_hashes_and_configured_boundaries(
    proposal: dict[str, Any], tmp_path: Path
) -> None:
    manifest = write_proposal_run(proposal, tmp_path, chunk_duration_s=30, snapshot_interval_s=30)
    assert manifest["contract_status"] == "proposal"
    assert not (tmp_path / "run.json").exists()
    assert manifest["chunk_duration_s"] == 30
    refs = [manifest["catalog"], *manifest["event_chunks"], *manifest["snapshot_chunks"]]
    for ref in refs:
        raw = (tmp_path / ref["path"]).read_bytes()
        assert len(raw) == ref["bytes"]
        assert hashlib.sha256(raw).hexdigest() == ref["sha256"]
    events = []
    for ref in manifest["event_chunks"]:
        payload = json.loads((tmp_path / ref["path"]).read_text())
        assert all(ref["start_s"] <= e["at_s"] < ref["end_s"] for e in payload["events"])
        events.extend(payload["events"])
    assert events == proposal["events"]


def test_transport_validates_once_preserves_inputs_and_publishes_manifest_last(
    proposal: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.exporter import wire_transport

    validator = Mock(wraps=validate_proposal)
    splitter = Mock(wraps=split_events)
    monkeypatch.setattr(wire_transport, "validate_proposal", validator)
    monkeypatch.setattr(wire_transport, "split_events", splitter)
    published: list[str] = []
    atomic_write = _atomic_write

    def track(path: Path, raw: bytes) -> None:
        published.append(path.name)
        atomic_write(path, raw)

    monkeypatch.setattr(wire_transport, "_atomic_write", track)
    (tmp_path / "inputs").mkdir()
    (tmp_path / "inputs/scenario.json").write_text("preserved")
    base_identity = {
        key: value for key, value in proposal["identity"].items() if key != "wire_version"
    }
    manifest = write_proposal_run(
        proposal,
        tmp_path,
        allow_existing_inputs=True,
        include_inline=True,
        metadata={"identity": base_identity},
    )
    assert validator.call_count == 1
    assert splitter.call_count == 1
    assert manifest["identity"] == proposal["identity"]
    assert published[-1] == "manifest.json"
    assert (tmp_path / "inputs/scenario.json").read_text() == "preserved"
    assert (tmp_path / manifest["inline"]["path"]).is_file()
    catalog = json.loads((tmp_path / manifest["catalog"]["path"]).read_bytes())
    assert not {"events", "actions", "snapshots"} & catalog.keys()


@pytest.mark.parametrize("seconds", [0, -1, True, float("inf"), 1 / 7])
def test_invalid_intervals_leave_output_empty(
    proposal: dict[str, Any], tmp_path: Path, seconds: Any
) -> None:
    with pytest.raises(ValueError, match="interval"):
        write_proposal_run(proposal, tmp_path, chunk_duration_s=seconds)
    assert list(tmp_path.iterdir()) == []


def test_existing_output_and_metadata_overrides_are_rejected(
    proposal: dict[str, Any], tmp_path: Path
) -> None:
    (tmp_path / "stale.json").write_text("old")
    with pytest.raises(ValueError, match="empty directory"):
        write_proposal_run(proposal, tmp_path)
    fresh = tmp_path / "fresh"
    with pytest.raises(ValueError, match="metadata"):
        write_proposal_run(proposal, fresh, metadata={"run_id": "wrong"})
    assert not fresh.exists()


@pytest.mark.parametrize("tampered", [True, False])
def test_manifest_provenance_must_match_identity(
    proposal: dict[str, Any], bundle: ContractBundle, tmp_path: Path, tampered: bool
) -> None:
    inputs = fixture_inputs(bundle, load_fixture(bundle.directory))
    provenance = inputs.scenario.provenance.model_dump(mode="json")
    if tampered:
        provenance["source_notes"] = "Unrelated provenance attached to an immutable run"
        with pytest.raises(ValueError, match="provenance"):
            write_proposal_run(proposal, tmp_path, metadata={"provenance": provenance})
        assert list(tmp_path.iterdir()) == []
    else:
        manifest = write_proposal_run(proposal, tmp_path, metadata={"provenance": provenance})
        assert manifest["provenance"] == provenance
        assert manifest["identity"] == proposal["identity"]


@pytest.mark.parametrize("interval", [237, 237.5])
def test_terminal_boundary_and_fractional_intervals_use_actual_fixture(
    proposal: dict[str, Any], tmp_path: Path, interval: float
) -> None:
    manifest = write_proposal_run(proposal, tmp_path, chunk_duration_s=interval)
    if interval == 237:
        last = manifest["event_chunks"][-1]
        assert (last["start_s"], last["end_s"]) == (474, 711)
        payload = json.loads((tmp_path / last["path"]).read_bytes())
        assert payload["events"] and all(event["at_s"] == 474 for event in payload["events"])
    else:
        assert [(row["start_s"], row["end_s"]) for row in manifest["event_chunks"]] == [
            (0, 237.5),
            (237.5, 475),
        ]


def test_failed_chunk_publish_never_exposes_completed_manifest(
    proposal: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.exporter import wire_transport

    atomic_write = _atomic_write

    def fail(path: Path, raw: bytes) -> None:
        if path.parent.name == "events":
            raise OSError("disk failure")
        atomic_write(path, raw)

    monkeypatch.setattr(wire_transport, "_atomic_write", fail)
    with pytest.raises(OSError, match="disk failure"):
        write_proposal_run(proposal, tmp_path)
    assert not (tmp_path / "manifest.json").exists()
