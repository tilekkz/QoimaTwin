"""Rehash every artifact before bounded semantic-cache reuse and captured-only reads."""

import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from fastapi import HTTPException
from pydantic import Field, ValidationError

from app.api.context import Json
from app.api.models import ArtifactId
from app.contracts.base import FrozenModel
from app.errors import InvalidInputError
from app.storage.artifacts import ArtifactCorruption, ArtifactStore
from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.api_manual_inputs import confined
from app.v3.api_receipt_identity import check_manifest_inventory, public_run_id, verified_response
from app.v3.api_receipt_inputs import FrozenReceiptProfile
from app.v3.receipt_run_validation import run_identity
from app.v3.receipt_transport import read_receipt_run
from app.v3.receipt_transport_schema import validate_manifest


class ReceiptFile(FrozenModel):
    path: Annotated[str, Field(min_length=1)]
    sha256: ArtifactId
    bytes: Annotated[int, Field(gt=0)]


class ReceiptIndex(FrozenModel):
    domain: Literal["qoima-v3-receipt-api-1"]
    run_id: ArtifactId
    native_run_id: ArtifactId
    input_bundle_id: ArtifactId
    input_hash: ArtifactId
    files: tuple[ReceiptFile, ...]


def run_index(store: ArtifactStore, identifier: str, frozen: FrozenReceiptProfile) -> Json:
    value = store.read_reference("runs", identifier)
    if value is None or value.get("domain") != "qoima-v3-receipt-api-1":
        raise HTTPException(404, "Unknown connected run")
    try:
        value = ReceiptIndex.from_data(value).model_dump(mode="json")
    except ValidationError as exc:
        raise ArtifactCorruption("invalid connected run index") from exc
    native = run_identity(frozen.metadata["input_hash"])
    expected = {
        "run_id": public_run_id(native, frozen.bundle_id),
        "native_run_id": native,
        "input_bundle_id": frozen.bundle_id,
        "input_hash": frozen.metadata["input_hash"],
    }
    if identifier != expected["run_id"] or any(value[k] != v for k, v in expected.items()):
        raise ArtifactCorruption(
            "connected run differs from its registered profile or native identity"
        )
    try:
        snapshot = store.read_json("bundles", frozen.bundle_id)
        keys = [snapshot["profile_sha256"], snapshot["frozen_inputs"]]
        keys.extend(row["sha256"] for row in [*snapshot["files"], *snapshot["conveyor_files"]])
        for key in set(keys):
            store.read_bytes("run_files", key)
    except InvalidInputError as exc:
        raise ArtifactCorruption("registered connected input evidence is unavailable") from exc
    return dict(value)


def file_bytes(store: ArtifactStore, index: Json, identifier: str) -> bytes:
    rows = [r for r in index["files"] if r["sha256"] == identifier]
    if not rows:
        raise HTTPException(404, "Unknown connected artifact file")
    try:
        raw = store.read_bytes("run_files", identifier)
    except InvalidInputError as exc:
        raise ArtifactCorruption("connected artifact file is unavailable") from exc
    if any(r["bytes"] != len(raw) for r in rows):
        raise ArtifactCorruption("connected artifact byte length mismatch")
    return raw


def _manifest(store: ArtifactStore, index: Json) -> Json:
    rows = [r for r in index["files"] if r["path"] == "manifest.json"]
    if len(rows) != 1:
        raise ArtifactCorruption("connected transport manifest missing")
    try:
        value = parse_json(file_bytes(store, index, rows[0]["sha256"]))
        validate_manifest(value)
        if value["run_id"] != index["native_run_id"] or value["input_hash"] != index["input_hash"]:
            raise ValueError("connected transport native identity mismatch")
        check_manifest_inventory(value, index)
    except ValueError as exc:
        raise ArtifactCorruption("connected manifest validation failed") from exc
    return dict(value)


def verified_artifact(
    store: ArtifactStore, identifier: str, frozen: FrozenReceiptProfile
) -> tuple[Json, Json]:
    index = run_index(store, identifier, frozen)
    _manifest(store, index)
    for row in index["files"]:
        confined(store.root, row["path"])
        file_bytes(store, index, row["sha256"])
    summary = parse_json(_validated(str(store.root), canonical_bytes(index)))
    return index, dict(summary)


@lru_cache(maxsize=8)
def _validated(store_root: str, index_bytes: bytes) -> bytes:
    store, index = ArtifactStore(Path(store_root)), parse_json(index_bytes)
    with tempfile.TemporaryDirectory(prefix="qoima-receipt-read-") as temporary:
        root = Path(temporary)
        for row in index["files"]:
            path = confined(root, row["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(file_bytes(store, index, row["sha256"]))
        try:
            run = read_receipt_run(root)
            if run["run_id"] != index["native_run_id"] or run["input_hash"] != index["input_hash"]:
                raise ValueError("connected native/public identity mismatch")
            result = {
                "response": verified_response(run, index),
                "captured_ticks": [c["tick"] for c in run["checkpoints"]],
                "manifest": parse_json((root / "manifest.json").read_bytes()),
            }
        except ValueError as exc:
            raise ArtifactCorruption("connected semantic artifact validation failed") from exc
    return canonical_bytes(result)


def verify_result(store: ArtifactStore, result: Json, frozen: FrozenReceiptProfile) -> Json:
    _, summary = verified_artifact(store, result["run_id"], frozen)
    expected: Json = summary["response"]
    if canonical_bytes(result) != canonical_bytes(expected):
        raise ArtifactCorruption(
            "cached connected result differs from actual verified observations"
        )
    return dict(expected)


def manifest(store: ArtifactStore, identifier: str, frozen: FrozenReceiptProfile) -> Json:
    index, summary = verified_artifact(store, identifier, frozen)
    return {"run_id": identifier, "transport": summary["manifest"], "files": index["files"]}


def status(store: ArtifactStore, identifier: str, frozen: FrozenReceiptProfile) -> Json:
    _, summary = verified_artifact(store, identifier, frozen)
    return dict(summary["response"])


def checkpoint(
    store: ArtifactStore, identifier: str, tick: int, frozen: FrozenReceiptProfile
) -> Json:
    index, summary = verified_artifact(store, identifier, frozen)
    if type(tick) is not int or tick not in summary["captured_ticks"]:
        raise InvalidInputError("tick is not an exactly captured connected checkpoint")
    for row in summary["manifest"]["checkpoint_chunks"]:
        if row["first_tick"] <= tick <= row["last_tick"]:
            items = parse_json(file_bytes(store, index, row["sha256"]))["items"]
            for item in items:
                if item["tick"] == tick:
                    return {"run_id": identifier, "checkpoint": item}
    raise ArtifactCorruption("captured connected checkpoint is missing")


def events(
    store: ArtifactStore, identifier: str, start: int, end: int, frozen: FrozenReceiptProfile
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
