"""Proposal replay windows carry a bounded full-base/delta chain for seeking."""

from pathlib import Path
from typing import Any

from app.api.models import CompareRequest
from app.api.readers import chunk_window, raw_file
from app.storage.artifacts import ArtifactStore


def _descriptor(store: ArtifactStore, at: int, *, encoding: str | None = None) -> dict[str, Any]:
    identifier = store.put_json("run_files", {"at_s": at})
    row = {
        "sha256": identifier,
        "bytes": len(store.read_bytes("run_files", identifier)),
        "path": f"{at}.json",
        "start_s": at,
        "end_s": at + 60,
    }
    if encoding is not None:
        row.update(encoding=encoding, base_at_s=at if encoding == "full" else at - 30)
    return row


def test_proposal_seek_includes_full_base_and_deltas(tmp_path: Path) -> None:
    store, identifier = ArtifactStore(tmp_path), "a" * 64
    catalog = _descriptor(store, -1)
    events = [_descriptor(store, at) for at in (0, 60, 120)]
    snapshots = [
        _descriptor(store, at, encoding="full" if at == 0 else "delta") for at in (0, 30, 60, 90)
    ]
    store.publish_reference(
        "runs",
        identifier,
        {
            "run_id": identifier,
            "catalog": catalog,
            "event_chunks": events,
            "snapshot_chunks": snapshots,
            "schema_version": "2.1",
            "contract_status": "proposal",
        },
    )
    result = chunk_window(store, identifier, 75, 1)
    assert [row["payload"]["at_s"] for row in result["snapshots"]] == [0, 30, 60]
    assert [row["payload"]["at_s"] for row in result["chunks"]] == [60]
    assert result["next_from_s"] == 120
    assert raw_file(store, identifier, snapshots[1]["sha256"])


def test_proposal_output_requires_explicit_opt_in() -> None:
    values = {"layout_version": "qoima-72x48-v2", "scenario_id": "a" * 64, "plan_id": "b" * 64}
    assert CompareRequest.model_validate(values).output_format == "2.0"
    assert CompareRequest.model_validate({**values, "output_format": "2.1-proposal"})
