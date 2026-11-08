"""Full strict cold reads, raw evidence rehash on every warm read, and exact captured views."""

import tempfile
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException

from app.errors import InvalidInputError
from app.storage.artifacts import ArtifactCorruption, ArtifactStore
from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.api_coordinator_binding import verified_registration
from app.v3.api_coordinator_evidence import OUTER_FILES, evidence_files
from app.v3.api_coordinator_identity import (
    check_manifest_inventory,
    public_run_id,
    verified_response,
)
from app.v3.api_coordinator_inputs import DOMAIN, FrozenCoordinatorProfile
from app.v3.api_coordinator_models import CoordinatorIndex
from app.v3.api_manual_inputs import confined
from app.v3.coordinator_run_identity import run_identity
from app.v3.coordinator_transport import read_coordinator_run
from app.v3.interface import Json


def profile_metadata(store: ArtifactStore, frozen: FrozenCoordinatorProfile) -> Json:
    verified_registration(store, frozen)
    return dict(parse_json(canonical_bytes(frozen.metadata)))


def known_run_reference(store: ArtifactStore, identifier: str) -> Json:
    try:
        value = store.read_reference("runs", identifier)
    except ValueError as exc:
        raise ArtifactCorruption("coordinator run reference is malformed") from exc
    if value is None:
        raise HTTPException(404, "Unknown coordinator run")
    if type(value) is not dict:
        raise ArtifactCorruption("coordinator run index must be an object")
    if value.get("domain") != DOMAIN:
        raise HTTPException(404, "Unknown coordinator run")
    return dict(value)


def run_index(store: ArtifactStore, identifier: str, frozen: FrozenCoordinatorProfile) -> Json:
    value = known_run_reference(store, identifier)
    try:
        value = CoordinatorIndex.from_data(value).model_dump(mode="json")
        native = run_identity(frozen.metadata["input_hash"])
        expected = {
            "run_id": public_run_id(native, frozen.bundle_id),
            "native_run_id": native,
            "input_bundle_id": frozen.bundle_id,
            "input_hash": frozen.metadata["input_hash"],
            "registry_common_hash": frozen.metadata["registry_common_hash"],
            "request_sha256": frozen.metadata["request_sha256"],
        }
        if identifier != expected["run_id"] or any(value[key] != v for key, v in expected.items()):
            raise ValueError("coordinator run differs from registered profile/native identity")
        names = [row["path"] for row in value["request_files"]]
        if len(names) != len(set(names)) or set(names) != set(OUTER_FILES):
            raise ValueError("coordinator request inventory differs")
    except (ValueError, TypeError, KeyError) as exc:
        raise ArtifactCorruption("invalid coordinator run index or registration binding") from exc
    return dict(value)


def file_bytes(store: ArtifactStore, index: Json, identifier: str) -> bytes:
    rows = [r for r in [*index["files"], *index["request_files"]] if r["sha256"] == identifier]
    if not rows:
        raise HTTPException(404, "Unknown coordinator artifact file")
    try:
        raw = store.read_bytes("run_files", identifier)
    except InvalidInputError as exc:
        raise ArtifactCorruption("coordinator artifact file is unavailable") from exc
    if any(r["bytes"] != len(raw) for r in rows):
        raise ArtifactCorruption("coordinator artifact byte length mismatch")
    return raw


def _manifest(store: ArtifactStore, index: Json) -> Json:
    rows = [row for row in index["files"] if row["path"] == "manifest.json"]
    if len(rows) != 1:
        raise ArtifactCorruption("coordinator native manifest is missing")
    try:
        value = parse_json(file_bytes(store, index, rows[0]["sha256"]))
        for key, expected in (
            ("run_id", index["native_run_id"]),
            ("input_hash", index["input_hash"]),
            ("registry_common_hash", index["registry_common_hash"]),
        ):
            if value[key] != expected:
                raise ValueError("coordinator native manifest identity mismatch")
        check_manifest_inventory(value, index)
    except (ValueError, TypeError, KeyError) as exc:
        raise ArtifactCorruption("coordinator manifest validation failed") from exc
    return dict(value)


def verified_artifact(
    store: ArtifactStore,
    identifier: str,
    frozen: FrozenCoordinatorProfile,
) -> tuple[Json, Json]:
    # Unknown public IDs remain 404 even if unrelated server registration is unavailable.
    index = run_index(store, identifier, frozen)
    snapshot = verified_registration(store, frozen)
    _manifest(store, index)
    try:
        for row in [*index["files"], *index["request_files"]]:
            confined(store.root, row["path"])
            file_bytes(store, index, row["sha256"])
    except ValueError as exc:
        raise ArtifactCorruption("invalid coordinator stored path or raw file") from exc
    summary = parse_json(
        _validated(str(store.root), canonical_bytes(index), canonical_bytes(snapshot)),
    )
    return index, dict(summary)


@lru_cache(maxsize=8)
def _validated(store_root: str, index_bytes: bytes, snapshot_bytes: bytes) -> bytes:
    store, index = ArtifactStore(Path(store_root)), parse_json(index_bytes)
    with tempfile.TemporaryDirectory(prefix="qoima-coordinator-read-") as temporary:
        root = Path(temporary)
        try:
            _restore(store, index, root)
            run = read_coordinator_run(root / "run")
            if run["run_id"] != index["native_run_id"] or run["input_hash"] != index["input_hash"]:
                raise ValueError("coordinator native/public identity mismatch")
            native_manifest = parse_json((root / "run/manifest.json").read_bytes())
            evidence_files(root, parse_json(snapshot_bytes), run)
            result = {
                "response": verified_response(run, index),
                "manifest": native_manifest,
                "captured_ticks": [row["tick"] for row in native_manifest["snapshot_chunks"]],
                "observed_until_tick": run["observed_until_tick"],
            }
        except (ValueError, TypeError, KeyError, OSError) as exc:
            raise ArtifactCorruption("coordinator semantic artifact validation failed") from exc
    return canonical_bytes(result)


def _restore(store: ArtifactStore, index: Json, root: Path) -> None:
    for group, target in (("files", root / "run"), ("request_files", root)):
        for row in index[group]:
            path = confined(target, row["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(file_bytes(store, index, row["sha256"]))


def verify_result(store: ArtifactStore, result: Json, frozen: FrozenCoordinatorProfile) -> Json:
    try:
        _, summary = verified_artifact(store, result["run_id"], frozen)
        expected: Json = summary["response"]
        if canonical_bytes(result) != canonical_bytes(expected):
            raise ValueError("cached coordinator result differs from actual verified observations")
    except (HTTPException, KeyError, TypeError, ValueError) as exc:
        raise ArtifactCorruption("invalid cached coordinator result") from exc
    return dict(expected)


def manifest(store: ArtifactStore, identifier: str, frozen: FrozenCoordinatorProfile) -> Json:
    index, summary = verified_artifact(store, identifier, frozen)
    return {
        "run_id": identifier,
        "transport": summary["manifest"],
        "files": index["files"],
        "request_files": index["request_files"],
    }


def status(store: ArtifactStore, identifier: str, frozen: FrozenCoordinatorProfile) -> Json:
    _, summary = verified_artifact(store, identifier, frozen)
    return dict(summary["response"])


def checkpoint(
    store: ArtifactStore,
    identifier: str,
    tick: int,
    frozen: FrozenCoordinatorProfile,
) -> Json:
    index, summary = verified_artifact(store, identifier, frozen)
    if type(tick) is not int or tick not in summary["captured_ticks"]:
        raise InvalidInputError("tick is not an exactly captured coordinator checkpoint")
    for row in summary["manifest"]["snapshot_chunks"]:
        if row["tick"] == tick:
            snapshot = parse_json(file_bytes(store, index, row["sha256"]))
            return {"run_id": identifier, "checkpoint": snapshot}
    raise ArtifactCorruption("captured coordinator checkpoint is missing")


def events(
    store: ArtifactStore,
    identifier: str,
    start: int,
    end: int,
    frozen: FrozenCoordinatorProfile,
) -> Json:
    index, summary = verified_artifact(store, identifier, frozen)
    if (
        type(start) is not int
        or type(end) is not int
        or not 0 <= start < end <= summary["observed_until_tick"] + 1
        or end - start > 60_000_000
    ):
        raise InvalidInputError("event window must be observed, half-open and at most 60 seconds")
    rows: list[Json] = []
    for descriptor in summary["manifest"]["event_chunks"]:
        if descriptor["end_tick"] > start and descriptor["start_tick"] < end:
            items = parse_json(file_bytes(store, index, descriptor["sha256"]))
            rows.extend(event for event in items if start <= event["tick"] < end)
    return {"run_id": identifier, "start_tick": start, "end_tick": end, "events": rows}
