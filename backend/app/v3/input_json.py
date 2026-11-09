"""Strict JSON parsing and offline, byte-exact package provenance validation."""

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn

from .input_models import SourceInventoryEntry, V3InputError
from .input_pin import PROVENANCE_SHA256, SOURCE_REVISION

PREFIX = "docs/v3/contract-proposals/"


def reject_constant(value: str) -> NoReturn:
    raise V3InputError(f"nonfinite JSON number: {value}")


def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise V3InputError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_json(raw: bytes, path: str) -> Any:
    try:
        value = json.loads(raw, object_pairs_hook=unique_pairs, parse_constant=reject_constant)
        check_finite(value, path)
        return value
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise V3InputError(f"{path}: {exc}") from exc


def check_finite(value: Any, path: str) -> None:
    import math

    if isinstance(value, float) and not math.isfinite(value):
        raise V3InputError(f"{path}: nonfinite JSON number")
    if isinstance(value, dict):
        for key, child in value.items():
            check_finite(child, f"{path}/{key}")
    if isinstance(value, list):
        for index, child in enumerate(value):
            check_finite(child, f"{path}/{index}")


def read_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise V3InputError(f"{path}: required source unreadable: {exc.strerror}") from exc


def verified_package(path: Path) -> tuple[tuple[SourceInventoryEntry, ...], dict[str, Any]]:
    raw = read_bytes(path / "provenance.json")
    if hashlib.sha256(raw).hexdigest() != PROVENANCE_SHA256:
        raise V3InputError("provenance.json: pinned inventory SHA256 mismatch")
    manifest = parse_json(raw, "provenance.json")
    if manifest["source_revision"] != SOURCE_REVISION:
        raise V3InputError("provenance.json/source_revision: unsupported revision")
    entries = tuple(
        SourceInventoryEntry(e["path"], e["raw_sha256"], e["bytes"]) for e in manifest["sources"]
    )
    documents: dict[str, Any] = {}
    for entry in entries:
        relative = PurePosixPath(entry.path)
        if relative.is_absolute() or ".." in relative.parts or "\\" in entry.path:
            raise V3InputError(f"{entry.path}: unsafe relative source path")
        raw = read_bytes(path / entry.path)
        if len(raw) != entry.bytes or hashlib.sha256(raw).hexdigest() != entry.raw_sha256:
            raise V3InputError(f"{entry.path}: pinned bytes/SHA256 mismatch")
        documents[entry.path] = parse_json(raw, entry.path)
    return entries, documents
