"""Authenticate a fixed upstream packet without executing its scripts or geometry."""

import re
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any, cast

from jsonschema import Draft202012Validator, SchemaError, ValidationError

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.offer_planning_cli_storage import read_regular, reject_links
from app.v3.physical_handoff_models import (
    SOURCE_REVISION,
    VALIDATION_SCOPE,
    VERSION,
    HandoffDocument,
    PhysicalHandoff,
)

PACKAGE_PATH = "docs/v3/contract-proposals/n2-n3-physical-interfaces-v1"
BUNDLE_SHA256 = "6a8e443c4d2f8cd7f219d012fbcdae1b7533ffa1571bed76e3e2d0d6938db854"
ARTIFACT_COUNT = 28
SOURCE_COUNT = 99
_FALSE_FLAGS = ("engine_operation", "operational_workflow_admitted", "backend_adoption_recorded")
_ADMISSION_FLAGS = (*_FALSE_FLAGS, "operational_admission", "actual_engine_run")
_CONSTRAINTS = (
    "scope",
    "open_actions",
    "required_new_runtime_interfaces",
    "api_refusals",
    "limitations",
    "API_guard",
    "required_before_execution",
)


def _object(value: object) -> dict[str, Any]:
    if type(value) is not dict:
        raise ValueError("Physical handoff JSON object required")
    return cast(dict[str, Any], value)


def _relative(value: object) -> str:
    if type(value) is not str or not re.fullmatch(r"[A-Za-z0-9._/-]+", value):
        raise ValueError("Safe relative physical source path required")
    path = PurePosixPath(value)
    devices = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"{p}{i}" for p in ("COM", "LPT") for i in range(1, 10)),
    }
    if (
        path.is_absolute()
        or path.as_posix() != value
        or any(
            part in {".", ".."} or part.endswith(".") or part.split(".")[0].upper() in devices
            for part in path.parts
        )
    ):
        raise ValueError("Physical source path alias or escape")
    return value


def _digest(value: object) -> str:
    if type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Exact lowercase SHA256 required")
    return value


def _bundle(raw: bytes) -> dict[str, Any]:
    if type(raw) is not bytes or sha256(raw).hexdigest() != BUNDLE_SHA256:
        raise ValueError("Physical handoff bundle anchor mismatch")
    bundle = _object(parse_json(raw))
    if bundle.get("source_kind") != "visual_fixture":
        raise ValueError("Physical handoff must retain visual_fixture source kind")
    if any(bundle.get(key) is not False for key in _FALSE_FLAGS):
        raise ValueError("Physical handoff cannot grant backend or operational admission")
    return bundle


def _inventory(bundle: dict[str, Any]) -> dict[str, tuple[str, int | None]]:
    artifacts, sources = _object(bundle["artifacts"]), _object(bundle["source_hashes"])
    if len(artifacts) != ARTIFACT_COUNT or len(sources) != SOURCE_COUNT:
        raise ValueError("Physical handoff inventory cardinality differs")
    result: dict[str, tuple[str, int | None]] = {}
    for name, value in artifacts.items():
        row = _object(value)
        if set(row) != {"sha256", "bytes"} or type(row["bytes"]) is not int or row["bytes"] < 0:
            raise ValueError("Exact artifact byte count and digest required")
        result[PACKAGE_PATH + "/" + _relative(name)] = (_digest(row["sha256"]), row["bytes"])
    for name, digest in sources.items():
        name = _relative(name)
        digest = _digest(digest)
        if name in result:
            if result[name][0] != digest:
                raise ValueError("Conflicting artifact/current-source digest")
        else:
            result[name] = (digest, None)
    if len({name.casefold() for name in result}) != len(result):
        raise ValueError("Physical handoff case alias")
    return dict(sorted(result.items()))


def _closed_package(root: Path, bundle: dict[str, Any]) -> None:
    package = root / PACKAGE_PATH
    expected = {"bundle.json", *_object(bundle["artifacts"])}
    directories = {
        str(parent)
        for name in expected
        for parent in PurePosixPath(name).parents
        if str(parent) != "."
    }
    actual: set[str] = set()
    for path in package.rglob("*"):
        reject_links(path)
        name = path.relative_to(package).as_posix()
        if path.is_dir():
            if name not in directories:
                raise ValueError("Unknown physical handoff directory")
        elif path.is_file():
            actual.add(name)
        else:
            raise ValueError("Physical handoff requires regular files")
    if actual != expected:
        raise ValueError("Physical handoff package inventory is not closed")


def _local_references(value: object) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"$ref", "$dynamicRef", "$recursiveRef"} and (
                type(child) is not str or not child.startswith("#")
            ):
                raise ValueError("Only local schema references are allowed")
            _local_references(child)
    elif isinstance(value, list):
        for child in value:
            _local_references(child)


def _schema(bundle: dict[str, Any], records: dict[str, HandoffDocument]) -> None:
    schema = _object(parse_json(records[PACKAGE_PATH + "/bundle.schema.json"].raw))
    _local_references(schema)
    try:
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(bundle)
    except (ValidationError, SchemaError) as exc:
        raise ValueError("Pinned physical bundle schema validation failed") from exc


def _sections(bundle: dict[str, Any], records: dict[str, HandoffDocument]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for group in ("sections", "extensions"):
        for name, value in _object(bundle[group]).items():
            row = _object(value)
            if set(row) != {"path", "sha256", "schema_id"} or name in result:
                raise ValueError("Physical section descriptor or namespace differs")
            document = records.get(PACKAGE_PATH + "/" + _relative(row["path"]))
            if document is None or document.sha256 != _digest(row["sha256"]):
                raise ValueError("Physical section raw reference differs")
            parsed = _object(parse_json(document.raw))
            if type(row["schema_id"]) is not str or parsed.get("schema_id") != row["schema_id"]:
                raise ValueError("Physical section schema identity differs")
            for flag in _ADMISSION_FLAGS:
                if flag in parsed and parsed[flag] is not False:
                    raise ValueError("Physical section remains reference-only")
            result[name] = parsed
    return result


def _report(
    bundle: dict[str, Any], documents: tuple[HandoffDocument, ...], sections: dict[str, Any]
) -> dict[str, Any]:
    return {
        "version": VERSION,
        "source_revision": SOURCE_REVISION,
        "bundle_sha256": BUNDLE_SHA256,
        "source_kind": bundle["source_kind"],
        "validation_scope": VALIDATION_SCOPE,
        "operational_admission": False,
        "engine_operation": False,
        "upstream_flags": {key: bundle[key] for key in _FALSE_FLAGS},
        "counts": {"artifacts": ARTIFACT_COUNT, "current_sources": SOURCE_COUNT},
        "sections": bundle["sections"],
        "extensions": bundle["extensions"],
        "documents": [_document_record(bundle, document) for document in documents],
        "constraints": {
            name: {key: value[key] for key in _CONSTRAINTS if key in value}
            for name, value in sections.items()
        },
        "upstream_section_flags": {
            name: {key: value[key] for key in _ADMISSION_FLAGS if key in value}
            for name, value in sections.items()
        },
        "not_validated": [
            "native_geometry",
            "continuous_motion",
            "traffic_and_resource_clocks",
            "ledger_credit",
            "operational_workflow",
            "shared_contract_2.1_adoption",
        ],
        "historical_epoch_policy": "Retain historical bytes; check only current root pins.",
    }


def _document_record(bundle: dict[str, Any], document: HandoffDocument) -> dict[str, Any]:
    roles = []
    prefix = PACKAGE_PATH + "/"
    if document.path.startswith(prefix) and document.path[len(prefix) :] in bundle["artifacts"]:
        roles.append("artifact")
    if document.path in bundle["source_hashes"]:
        roles.append("current_source")
    return {
        "path": document.path,
        "bytes": len(document.raw),
        "sha256": document.sha256,
        "roles": roles,
    }


def _reconstruct(bundle_raw: bytes, documents: tuple[HandoffDocument, ...]) -> PhysicalHandoff:
    bundle = _bundle(bundle_raw)
    expected = _inventory(bundle)
    if type(documents) is not tuple or len(documents) != len(expected):
        raise ValueError("Immutable complete physical document records required")
    for document, (path, (digest, size)) in zip(documents, expected.items(), strict=True):
        if type(document) is not HandoffDocument:
            raise ValueError("Exact physical document record required")
        if type(document.path) is not str or type(document.raw) is not bytes:
            raise ValueError("Exact immutable physical path and bytes required")
        if document.path != path or _digest(document.sha256) != digest:
            raise ValueError("Physical document order, path or digest differs")
        if sha256(document.raw).hexdigest() != digest or (
            size is not None and len(document.raw) != size
        ):
            raise ValueError("Physical source raw bytes differ")
        if path.startswith(PACKAGE_PATH + "/") and path.endswith(".json"):
            parse_json(document.raw)
    records = {d.path: d for d in documents}
    _schema(bundle, records)
    sections = _sections(bundle, records)
    frozen = canonical_bytes(_report(bundle, documents, sections))
    return PhysicalHandoff(
        SOURCE_REVISION, bundle_raw, documents, frozen, sha256(frozen).hexdigest()
    )


def load_physical_handoff(root: Path) -> PhysicalHandoff:
    """Read only the explicit caller root, with a fixed raw upstream anchor."""
    reject_links(root)
    if not root.is_dir():
        raise ValueError("Explicit physical assets root directory required")
    raw = read_regular(root / PACKAGE_PATH / "bundle.json")
    bundle = _bundle(raw)
    expected = _inventory(bundle)
    _closed_package(root, bundle)
    documents = tuple(
        HandoffDocument(path, read_regular(root / path), digest)
        for path, (digest, _) in expected.items()
    )
    return _reconstruct(raw, documents)


def verify_physical_handoff(value: PhysicalHandoff) -> PhysicalHandoff:
    """Freshly authenticate retained bytes; no trusted parsed dictionaries or cache."""
    if type(value) is not PhysicalHandoff:
        raise ValueError("Exact typed physical handoff required")
    if (
        type(value.source_revision) is not str
        or type(value.frozen_bytes) is not bytes
        or type(value.input_hash) is not str
    ):
        raise ValueError("Exact immutable physical descriptor fields required")
    fresh = _reconstruct(value.bundle_raw, value.documents)
    if fresh != value:
        raise ValueError("Retained physical descriptor differs from fresh authority")
    return fresh


def handoff_section(value: PhysicalHandoff, name: str) -> dict[str, Any]:
    """Return a disposable parsed copy after fresh byte authority verification."""
    fresh = verify_physical_handoff(value)
    if type(name) is not str:
        raise ValueError("Exact physical section name required")
    sections = _sections(_bundle(fresh.bundle_raw), {d.path: d for d in fresh.documents})
    if name not in sections:
        raise ValueError("Unknown physical handoff section")
    return _object(sections[name])
