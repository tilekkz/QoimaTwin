"""The API seek keeps the transport's bounded read contract across backward seeks."""

from pathlib import Path
from typing import Any

import pytest

from app.storage.artifacts import ArtifactCorruption, ArtifactStore
from app.storage.canonical_json import sha256_hex
from app.v3.api_manual_identity import verified_response
from app.v3.api_manual_inputs import DOMAIN, EXPORT_VERSION
from app.v3.api_manual_readers import manifest as read_manifest
from app.v3.api_manual_readers import run_index, seek, verify_result
from app.v3.execution import ManualEngine
from app.v3.run_export import build_manual_run
from app.v3.run_replay import replay_manual
from app.v3.run_transport import write_manual_run
from tests.v3.test_run_fixtures import manual_profile


def stored_run(tmp_path: Path) -> tuple[ArtifactStore, str, dict[str, Any], dict[str, Any]]:
    profile, graph, document = manual_profile()
    outcome = ManualEngine(profile, graph, check_invariants=True).run(25_000_000, 40_000_000)
    run = build_manual_run(
        profile,
        graph,
        outcome,
        graph_document=document,
        end_tick_limit=40_000_000,
        snapshot_interval_ticks=10_000_000,
    )
    root = tmp_path / "source"
    manifest = write_manual_run(run, root / "run", max_chunk_bytes=5000)
    store, files = ArtifactStore(tmp_path / "store"), []
    for path in sorted(root.rglob("*.json")):
        raw = path.read_bytes()
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": len(raw),
                "sha256": store.put_bytes("run_files", raw),
            }
        )
    run_id = sha256_hex(
        {
            "domain": DOMAIN,
            "native_run_id": run["run_id"],
            "inputs": "b" * 64,
            "export": EXPORT_VERSION,
        }
    )
    store.publish_reference(
        "runs",
        run_id,
        {
            "domain": DOMAIN,
            "run_id": run_id,
            "native_run_id": run["run_id"],
            "input_bundle_id": "b" * 64,
            "files": files,
        },
    )
    return store, run_id, run, manifest


def test_seek_skips_graph_and_unrelated_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, run_id, run, manifest = stored_run(tmp_path)
    reads: set[str] = set()
    original = store.read_bytes

    def tracked(kind: str, identifier: str) -> bytes:
        reads.add(identifier)
        return original(kind, identifier)

    monkeypatch.setattr(store, "read_bytes", tracked)
    result = seek(store, run_id, 18_000_000)
    assert result["state"] == replay_manual(run, 18_000_000)
    assert manifest["graph_document"]["sha256"] not in reads
    assert sum(row["sha256"] in reads for row in manifest["snapshot_chunks"]) == 1
    assert sum(row["sha256"] in reads for row in manifest["event_chunks"]) < len(
        manifest["event_chunks"]
    )


def test_api_seek_is_repeatable_and_keeps_business_boundary(tmp_path: Path) -> None:
    store, run_id, run, _ = stored_run(tmp_path)
    observations = [seek(store, run_id, tick * 1_000_000)["state"] for tick in (10, 26, 5, 26)]
    assert observations[1] == observations[3] == replay_manual(run, 26_000_000)
    assert observations[1]["stock_units"] == [["SKU1", 24]]
    assert observations[1]["status"] == "partial"  # paid return continues until 33s


def test_api_rejects_coherent_index_under_foreign_semantic_id(tmp_path: Path) -> None:
    store, run_id, _, _ = stored_run(tmp_path)
    index = store.read_reference("runs", run_id)
    index["run_id"] = "e" * 64
    store.publish_reference("runs", index["run_id"], index)
    with pytest.raises(ArtifactCorruption):
        run_index(store, index["run_id"])


def test_api_rejects_cached_response_disagreeing_with_verified_run(tmp_path: Path) -> None:
    store, run_id, _, _ = stored_run(tmp_path)
    cached = {
        "status": "failed",
        "run_id": run_id,
        "native_run_id": "f" * 64,
        "input_hash": "wrong",
        "source_label": "visual_fixture",
        "full_v3_warehouse": True,
        "frontend_adapter": True,
        "manifest": "wrong",
    }
    with pytest.raises(ArtifactCorruption):
        verify_result(store, cached)


def test_api_rejects_manifest_bound_to_another_native_run(tmp_path: Path) -> None:
    store, run_id, _, transport = stored_run(tmp_path)
    index = store.read_reference("runs", run_id)
    transport["run_id"] = "c" * 64
    wrong_id = store.put_json("run_files", transport)
    for row in index["files"]:
        if row["path"] == "run/manifest.json":
            row.update(sha256=wrong_id, bytes=len(store.read_bytes("run_files", wrong_id)))
    # A valid checksum envelope is not a semantic domain/native-run binding.
    store.path("runs", run_id).unlink()
    store.publish_reference("runs", run_id, index)
    with pytest.raises(ArtifactCorruption):
        read_manifest(store, run_id)


@pytest.mark.parametrize("damage", ["missing", "size", "hash", "duplicate"])
def test_manifest_inventory_must_match_transport_descriptors(tmp_path: Path, damage: str) -> None:
    store, run_id, _, _ = stored_run(tmp_path)
    index = store.read_reference("runs", run_id)
    row = next(row for row in index["files"] if row["path"] == "run/metadata.json")
    if damage == "missing":
        index["files"].remove(row)
    elif damage == "size":
        row["bytes"] += 1
    elif damage == "hash":
        row.update(sha256=store.put_json("run_files", {}), bytes=2)
    else:
        index["files"].append(dict(row))
    store.path("runs", run_id).unlink()
    store.publish_reference("runs", run_id, index)
    with pytest.raises(ArtifactCorruption):
        read_manifest(store, run_id)


def test_reuse_skips_full_replay_but_rechecks_every_raw_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.v3 import run_transport

    store, run_id, run, transport = stored_run(tmp_path)
    index = run_index(store, run_id)
    response = verified_response(run, index)
    calls = 0
    original = run_transport.read_manual_run

    def tracked(root: Path) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return original(root)

    monkeypatch.setattr(run_transport, "read_manual_run", tracked)
    assert verify_result(store, response) == verify_result(store, response) == response
    assert calls == 1
    store.path("run_files", transport["graph_document"]["sha256"]).write_bytes(b"corrupt")
    with pytest.raises(ArtifactCorruption):
        verify_result(store, response)
