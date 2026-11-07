"""Verified domain-scoped immutable files and the owner's repeatable seek reader."""

import tempfile
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException

from app.errors import InvalidInputError
from app.storage.artifacts import ArtifactCorruption, ArtifactStore
from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.api_manual_identity import (
    check_manifest_inventory,
    public_run_id,
    verified_response,
)
from app.v3.api_manual_inputs import DOMAIN, Json, confined


def run_index(store: ArtifactStore, run_id: str) -> Json:
    value = store.read_reference("runs", run_id)
    if value is None or value.get("domain") != DOMAIN:
        raise HTTPException(404, "Unknown manual run")
    if value["run_id"] != run_id or run_id != public_run_id(
        value["native_run_id"], value["input_bundle_id"]
    ):
        raise ArtifactCorruption("manual run identity mismatch")
    return dict(value)


def file_bytes(store: ArtifactStore, index: Json, artifact_id: str) -> bytes:
    rows = [row for row in index["files"] if row["sha256"] == artifact_id]
    if not rows:
        raise HTTPException(404, "Unknown manual run file")
    raw = store.read_bytes("run_files", artifact_id)
    if any(row["bytes"] != len(raw) for row in rows):
        raise ArtifactCorruption("manual file length mismatch")
    return raw


def manifest(store: ArtifactStore, run_id: str) -> Json:
    from app.v3.run_transport_schema import validate_transport

    index = run_index(store, run_id)
    rows = [row for row in index["files"] if row["path"] == "run/manifest.json"]
    if len(rows) != 1:
        raise ArtifactCorruption("manual transport manifest missing")
    value = parse_json(file_bytes(store, index, rows[0]["sha256"]))
    try:
        validate_transport(value, "manifest")
        if value["run_id"] != index["native_run_id"]:
            raise ValueError("manual manifest belongs to another native run")
        check_manifest_inventory(value, index)
    except ValueError as exc:
        raise ArtifactCorruption("manual manifest validation failed") from exc
    return {"domain": DOMAIN, "run_id": run_id, "transport": value, "files": index["files"]}


def _restore(store: ArtifactStore, index: Json, root: Path, paths: set[str] | None = None) -> None:
    for row in index["files"]:
        if paths is not None and row["path"] not in paths:
            continue
        path = confined(root, row["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(file_bytes(store, index, row["sha256"]))


def verify_result(
    store: ArtifactStore, result: Json, *, expected_bundle_id: str | None = None
) -> Json:
    index = run_index(store, result["run_id"])
    if expected_bundle_id is not None and index["input_bundle_id"] != expected_bundle_id:
        raise ArtifactCorruption("manual response belongs to another frozen input bundle")
    manifest(store, result["run_id"])
    for row in index["files"]:
        file_bytes(store, index, row["sha256"])
    expected = parse_json(_validated_response(str(store.root), canonical_bytes(index)))
    if result != expected:
        raise ArtifactCorruption("cached manual response disagrees with verified run")
    return dict(expected)


@lru_cache(maxsize=8)
def _validated_response(store_root: str, index_bytes: bytes) -> bytes:
    from app.v3.run_transport import read_manual_run

    store, index = ArtifactStore(Path(store_root)), parse_json(index_bytes)
    with tempfile.TemporaryDirectory(prefix="qoima-manual-read-") as temporary:
        root = Path(temporary)
        _restore(store, index, root)
        try:
            run = read_manual_run(root / "run")
            if run["run_id"] != index["native_run_id"]:
                raise ValueError("manual run identity mismatch")
            expected = verified_response(run, index)
        except ValueError as exc:
            raise ArtifactCorruption("manual run validation failed") from exc
    return canonical_bytes(expected)


def seek(store: ArtifactStore, run_id: str, cutoff_tick: int) -> Json:
    from app.v3.run_transport import seek_manual_run

    index = run_index(store, run_id)
    transport = manifest(store, run_id)["transport"]
    if type(cutoff_tick) is not int or not 0 <= cutoff_tick <= transport["observed_until_tick"]:
        raise InvalidInputError("manual seek cutoff is outside the observed timeline")
    with tempfile.TemporaryDirectory(prefix="qoima-manual-seek-") as temporary:
        root = Path(temporary)
        try:
            _restore(store, index, root, _seek_paths(transport, cutoff_tick))
            state = seek_manual_run(root / "run", cutoff_tick)
        except ValueError as exc:
            raise ArtifactCorruption("manual replay validation failed") from exc
    return {"run_id": run_id, "cutoff_tick": cutoff_tick, "state": state}


def _seek_paths(transport: Json, cutoff_tick: int) -> set[str]:
    from app.v3.run_transport_schema import validate_transport

    validate_transport(transport, "manifest")
    candidates = [d for d in transport["snapshot_chunks"] if d["first_tick"] <= cutoff_tick]
    checkpoint = max(candidates, key=lambda row: row["first_tick"])
    descriptors = [transport["metadata"], checkpoint]
    descriptors.extend(
        row
        for row in transport["event_chunks"]
        if row["last_tick"] >= checkpoint["first_tick"] and row["first_tick"] <= cutoff_tick
    )
    return {"run/manifest.json", *("run/" + row["path"] for row in descriptors)}
