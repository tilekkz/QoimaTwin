"""Rehash every artifact before bounded semantic-cache reuse and captured-only reads."""

import tempfile
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException
from pydantic import ValidationError

from app.api.context import Json
from app.errors import InvalidInputError
from app.storage.artifacts import ArtifactCorruption, ArtifactStore
from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.api_manual_inputs import confined
from app.v3.api_whole_binding import verified_registration
from app.v3.api_whole_evidence import OUTER_FILES, evidence_files
from app.v3.api_whole_identity import check_manifest_inventory, public_run_id, verified_response
from app.v3.api_whole_inputs import FrozenWholeProfile
from app.v3.api_whole_models import WholeIndex
from app.v3.whole_run_validation import run_identity
from app.v3.whole_transport import read_whole_run
from app.v3.whole_transport_schema import validate_manifest


def profile_metadata(store: ArtifactStore, frozen: FrozenWholeProfile) -> Json:
    verified_registration(store, frozen)
    return dict(parse_json(canonical_bytes(frozen.metadata)))


def run_index(store: ArtifactStore, identifier: str, frozen: FrozenWholeProfile) -> Json:
    value = store.read_reference("runs", identifier)
    if value is None or value.get("domain") != "qoima-v3-whole-api-1":
        raise HTTPException(404, "Unknown whole run")
    try:
        value = WholeIndex.from_data(value).model_dump(mode="json")
    except ValidationError as exc:
        raise ArtifactCorruption("invalid whole run index") from exc
    native = run_identity(frozen.metadata["input_hash"])
    expected = {
        "run_id": public_run_id(native, frozen.bundle_id),
        "native_run_id": native,
        "input_bundle_id": frozen.bundle_id,
        "input_hash": frozen.metadata["input_hash"],
        "physical_input_hash": frozen.metadata["physical_input_hash"],
        "request_sha256": frozen.metadata["request_sha256"],
    }
    if identifier != expected["run_id"] or any(value[k] != v for k, v in expected.items()):
        raise ArtifactCorruption("whole run differs from its registered profile or native identity")
    names = [row["path"] for row in value["request_files"]]
    if len(names) != len(set(names)) or set(names) != set(OUTER_FILES):
        raise ArtifactCorruption("whole request inventory differs from required evidence")
    return dict(value)


def file_bytes(store: ArtifactStore, index: Json, identifier: str) -> bytes:
    rows = [r for r in [*index["files"], *index["request_files"]] if r["sha256"] == identifier]
    if not rows:
        raise HTTPException(404, "Unknown whole artifact file")
    try:
        raw = store.read_bytes("run_files", identifier)
    except InvalidInputError as exc:
        raise ArtifactCorruption("whole artifact file is unavailable") from exc
    if any(r["bytes"] != len(raw) for r in rows):
        raise ArtifactCorruption("whole artifact byte length mismatch")
    return raw


def _manifest(store: ArtifactStore, index: Json) -> Json:
    rows = [r for r in index["files"] if r["path"] == "manifest.json"]
    if len(rows) != 1:
        raise ArtifactCorruption("whole transport manifest missing")
    try:
        value = parse_json(file_bytes(store, index, rows[0]["sha256"]))
        validate_manifest(value)
        if value["run_id"] != index["native_run_id"] or value["input_hash"] != index["input_hash"]:
            raise ValueError("whole transport native identity mismatch")
        check_manifest_inventory(value, index)
    except ValueError as exc:
        raise ArtifactCorruption("whole manifest validation failed") from exc
    return dict(value)


def verified_artifact(
    store: ArtifactStore, identifier: str, frozen: FrozenWholeProfile
) -> tuple[Json, Json]:
    snapshot = verified_registration(store, frozen)
    index = run_index(store, identifier, frozen)
    _manifest(store, index)
    for row in [*index["files"], *index["request_files"]]:
        confined(store.root, row["path"])
        file_bytes(store, index, row["sha256"])
    summary = parse_json(
        _validated(str(store.root), canonical_bytes(index), canonical_bytes(snapshot))
    )
    return index, dict(summary)


@lru_cache(maxsize=8)
def _validated(store_root: str, index_bytes: bytes, snapshot_bytes: bytes) -> bytes:
    store, index = ArtifactStore(Path(store_root)), parse_json(index_bytes)
    with tempfile.TemporaryDirectory(prefix="qoima-whole-read-") as temporary:
        root = Path(temporary)
        _restore(store, index, root)
        try:
            run = read_whole_run(root / "run")
            if run["run_id"] != index["native_run_id"] or run["input_hash"] != index["input_hash"]:
                raise ValueError("whole native/public identity mismatch")
            manifest_value = parse_json((root / "run/manifest.json").read_bytes())
            evidence_files(root, parse_json(snapshot_bytes), run, manifest_value)
            result = {
                "response": verified_response(run, index),
                "captured_ticks": [c["tick"] for c in run["checkpoints"]],
                "manifest": manifest_value,
            }
        except ValueError as exc:
            raise ArtifactCorruption("whole semantic artifact validation failed") from exc
    return canonical_bytes(result)


def _restore(store: ArtifactStore, index: Json, root: Path) -> None:
    for group, target in (("files", root / "run"), ("request_files", root)):
        for row in index[group]:
            path = confined(target, row["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(file_bytes(store, index, row["sha256"]))


def verify_result(store: ArtifactStore, result: Json, frozen: FrozenWholeProfile) -> Json:
    _, summary = verified_artifact(store, result["run_id"], frozen)
    expected: Json = summary["response"]
    if canonical_bytes(result) != canonical_bytes(expected):
        raise ArtifactCorruption("cached whole result differs from actual verified observations")
    return dict(expected)


def manifest(store: ArtifactStore, identifier: str, frozen: FrozenWholeProfile) -> Json:
    index, summary = verified_artifact(store, identifier, frozen)
    return {
        "run_id": identifier,
        "transport": summary["manifest"],
        "files": index["files"],
        "request_files": index["request_files"],
    }


def status(store: ArtifactStore, identifier: str, frozen: FrozenWholeProfile) -> Json:
    _, summary = verified_artifact(store, identifier, frozen)
    return dict(summary["response"])


def checkpoint(
    store: ArtifactStore, identifier: str, tick: int, frozen: FrozenWholeProfile
) -> Json:
    index, summary = verified_artifact(store, identifier, frozen)
    if type(tick) is not int or tick not in summary["captured_ticks"]:
        raise InvalidInputError("tick is not an exactly captured whole checkpoint")
    for row in summary["manifest"]["checkpoint_chunks"]:
        if row["first_tick"] <= tick <= row["last_tick"]:
            items = parse_json(file_bytes(store, index, row["sha256"]))["items"]
            for item in items:
                if item["tick"] == tick:
                    return {"run_id": identifier, "checkpoint": item}
    raise ArtifactCorruption("captured whole checkpoint is missing")


def events(
    store: ArtifactStore, identifier: str, start: int, end: int, frozen: FrozenWholeProfile
) -> Json:
    index, summary = verified_artifact(store, identifier, frozen)
    maximum = summary["manifest"]["observed_until_tick"] + 1
    if (
        type(start) is not int
        or type(end) is not int
        or not 0 <= start < end <= maximum
        or end - start > 60_000_000
    ):
        raise InvalidInputError("event window must be observed, half-open and at most 60 seconds")
    rows: list[Json] = []
    for descriptor in summary["manifest"]["event_chunks"]:
        if descriptor["last_tick"] >= start and descriptor["first_tick"] < end:
            items = parse_json(file_bytes(store, index, descriptor["sha256"]))["items"]
            rows.extend(e for e in items if start <= e["tick"] < end)
    return {"run_id": identifier, "start_tick": start, "end_tick": end, "events": rows}
