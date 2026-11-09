"""Byte-exact loading of the separately pinned C11 planning package (ADR 0054).

The existing 14-file V3 baseline package is verified with its own unchanged loader; C11
documents only bind to it by raw hashes. Documents are kept as raw bytes and every accessor
returns a fresh parse, so callers can never mutate the pinned source.
"""

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any

from app.storage.canonical_json import canonical_bytes
from app.v3.adaptation_pin import (
    EVALUATION_PATH,
    HORIZON_PATHS,
    INPUT_PATH,
    PREFIX,
    PROVENANCE_SHA256,
    SOURCE_REVISION,
)
from app.v3.input_json import parse_json, verified_package
from app.v3.input_models import V3InputError


class AdaptationSourceError(ValueError):
    """The C11 planning package is not the exact pinned source or does not bind to it."""


@dataclass(frozen=True, slots=True)
class AdaptationEntry:
    path: str
    raw_sha256: str
    bytes: int
    git_blob_sha1: str


@dataclass(frozen=True, slots=True)
class AdaptationPackage:
    source_revision: str
    entries: tuple[AdaptationEntry, ...]
    baseline_assignment_sha256: str
    baseline_input_sha256: str
    comparison_inputs_sha256_verified: bool
    _raw: Mapping[str, bytes]
    _base: Mapping[str, bytes]

    def document(self, path: str) -> Any:
        """A fresh strict parse of one pinned C11 document."""
        return parse_json(self._raw[path], path)

    def horizon_document(self, periods: int) -> Any:
        if type(periods) is not int or periods not in HORIZON_PATHS:
            raise AdaptationSourceError(f"unsupported planning horizon {periods!r}")
        return self.document(HORIZON_PATHS[periods])

    def base_document(self, name: str) -> Any:
        """Fresh parse of the immutable canonical baseline captured after pin verification."""
        return parse_json(self._base[PREFIX + name], PREFIX + name)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _blob(raw: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(raw) + raw, usedforsecurity=False).hexdigest()


def _read(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise AdaptationSourceError(f"{path}: unreadable pinned source") from exc


def _entries(package: Path, manifest: Any) -> tuple[tuple[AdaptationEntry, ...], dict[str, bytes]]:
    entries, raw = [], {}
    for row in manifest["sources"]:
        entry = AdaptationEntry(row["path"], row["raw_sha256"], row["bytes"], row["git_blob_sha1"])
        relative = PurePosixPath(entry.path)
        if relative.is_absolute() or ".." in relative.parts or "\\" in entry.path:
            raise AdaptationSourceError(f"{entry.path}: unsafe relative source path")
        data = _read(package / entry.path)
        found = (len(data), _sha(data), _blob(data))
        if found != (entry.bytes, entry.raw_sha256, entry.git_blob_sha1):
            raise AdaptationSourceError(f"{entry.path}: pinned bytes/SHA256/blob mismatch")
        entries.append(entry)
        raw[entry.path] = data
    expected = {INPUT_PATH, EVALUATION_PATH, *HORIZON_PATHS.values()}
    if set(raw) != expected or len(entries) != len(expected):
        raise AdaptationSourceError("C11 package must pin exactly the six planning documents")
    return tuple(entries), raw


def _manifest(package: Path) -> Any:
    raw = _read(package / "provenance.json")
    if _sha(raw) != PROVENANCE_SHA256:
        raise AdaptationSourceError("provenance.json: pinned C11 provenance SHA256 mismatch")
    manifest = parse_json(raw, "provenance.json")
    if manifest["source_revision"] != SOURCE_REVISION:
        raise AdaptationSourceError("provenance.json: unsupported C11 source revision")
    if manifest["comparison_inputs_sha256_method_established"] is not False:
        raise AdaptationSourceError("comparison_inputs_sha256 method is not established")
    return manifest


def load_adaptation_package(
    package: Path, base: Path, vehicle: Path | None = None
) -> AdaptationPackage:
    """Verify the C11 pin, the unchanged baseline package and every declared hash binding."""
    manifest = _manifest(package)
    entries, raw = _entries(package, manifest)
    try:
        base_entries, documents = verified_package(base)
    except V3InputError as exc:
        raise AdaptationSourceError(f"baseline package rejected: {exc}") from exc
    base_hashes = {entry.path: entry.raw_sha256 for entry in base_entries}
    result = AdaptationPackage(
        SOURCE_REVISION,
        entries,
        base_hashes[PREFIX + "baseline-assignment-v3.json"],
        base_hashes[PREFIX + "baseline-input-v3.json"],
        False,
        MappingProxyType(raw),
        MappingProxyType({path: canonical_bytes(value) for path, value in documents.items()}),
    )
    _bind_baseline(manifest, result)
    vehicle_root = vehicle or base.parent / "v3-vehicle-proposal"
    _bind_fingerprints(result, base_hashes, vehicle_root)
    return result


def _bind_baseline(manifest: Any, package: AdaptationPackage) -> None:
    declared = manifest["baseline_package"]
    pinned = (package.baseline_assignment_sha256, package.baseline_input_sha256)
    if (declared["baseline_assignment_sha256"], declared["baseline_input_sha256"]) != pinned:
        raise AdaptationSourceError("manifest baseline binding differs from the baseline pin")
    source = package.document(INPUT_PATH)
    if (source["baseline_assignment_sha256"], source["baseline_input_sha256"]) != pinned:
        raise AdaptationSourceError("adaptation input does not bind the pinned baseline")
    evaluation = package.document(EVALUATION_PATH)
    if evaluation["frozen_inputs_sha256"] != _sha(package._raw[INPUT_PATH]):
        raise AdaptationSourceError("evaluation does not bind the exact adaptation input bytes")


def _bind_fingerprints(package: AdaptationPackage, base: dict[str, str], vehicle: Path) -> None:
    expected = package.document(INPUT_PATH)["source_fingerprints"]
    for path in HORIZON_PATHS.values():
        if package.document(path)["source_fingerprints"] != expected:
            raise AdaptationSourceError(f"{path}: source fingerprints differ from the input")
    for row in expected:
        found = base.get(row["path"])
        if found is None:
            found = _sha(_read(vehicle / row["path"]))
        if found != row["sha256"]:
            raise AdaptationSourceError(f"{row['path']}: C11 source fingerprint mismatch")
