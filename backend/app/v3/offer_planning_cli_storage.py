"""Exclusive bounded files, immutable raw request and a closed local bundle inventory."""

from dataclasses import astuple
from hashlib import sha256
from pathlib import Path
from typing import Any

from app.errors import require_empty_output
from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.offer_planning_cli_models import (
    RAW_NAMES,
    REQUEST_VERSION,
    STAGES,
    PlanningFiles,
    versions,
)
from app.v3.workload_policy import fields

MAX_BYTES = 128 * 1024 * 1024


def descriptor(path: str, raw: bytes) -> dict[str, Any]:
    return {"path": path, "bytes": len(raw), "sha256": sha256(raw).hexdigest()}


def reject_links(path: Path) -> None:
    for item in (path, *path.parents):
        if item.is_symlink() or item.is_junction():
            raise ValueError("Offer planning paths must not traverse links or junctions")


def read_regular(path: Path) -> bytes:
    reject_links(path)
    if not path.is_file() or path.stat().st_nlink != 1 or path.stat().st_size > MAX_BYTES:
        raise ValueError("Bounded regular unshared planning file required")
    return path.read_bytes()


def put(root: Path, name: str, raw: bytes) -> dict[str, Any]:
    path = root / name
    reject_links(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)
    return descriptor(name, raw)


def prepare_output(root: Path) -> None:
    reject_links(root)
    require_empty_output(root)
    root.mkdir(parents=True, exist_ok=True)
    # Claim the required raw directory before a losing writer can publish failure evidence.
    (root / "raw").mkdir(exist_ok=False)


def request_record(model: str, raw: dict[str, bytes]) -> dict[str, Any]:
    if type(model) is not str or model not in {"mean28", "hgb"}:
        raise ValueError("Explicit mean28 or hgb model required")
    return {
        "version": REQUEST_VERSION,
        "model": model,
        "producer_versions": versions(),
        "raw_inputs": [descriptor("raw/" + name, raw[name]) for name in RAW_NAMES],
        "operational_admission": False,
        "actual_test_stream": False,
    }


def freeze_request(paths: PlanningFiles, model: str, root: Path) -> tuple[dict[str, bytes], bytes]:
    raw: dict[str, bytes] = {}
    for name, path in zip(RAW_NAMES, astuple(paths), strict=True):
        raw[name] = read_regular(path)
        put(root, "raw/" + name, raw[name])
    request = canonical_bytes(request_record(model, raw))
    put(root, "request.json", request)
    return raw, request


def checked_file(root: Path, name: str, value: object) -> bytes:
    row = fields(value, {"path", "bytes", "sha256"})
    raw = read_regular(root / name)
    if canonical_bytes(row) != canonical_bytes(descriptor(name, raw)):
        raise ValueError("Planning descriptor or bytes changed: " + name)
    return raw


def closed_inventory(root: Path) -> None:
    reject_links(root)
    if not root.is_dir():
        raise ValueError("Planning bundle directory required")
    expected = {"raw", "request.json", "observations.json", "manifest.json"}
    expected.update(name + ".json" for name in STAGES)
    if {path.name for path in root.iterdir()} != expected:
        raise ValueError("Planning bundle has unknown or missing files")
    reject_links(root / "raw")
    if not (root / "raw").is_dir() or {p.name for p in (root / "raw").iterdir()} != set(RAW_NAMES):
        raise ValueError("Raw planning inventory differs")


def canonical_document(raw: bytes) -> Any:
    value = parse_json(raw)
    if canonical_bytes(value) != raw:
        raise ValueError("Canonical planning metadata required")
    return value
