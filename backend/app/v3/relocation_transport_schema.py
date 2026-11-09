"""Closed N1 file descriptors reuse physical bounds without adopting the C65 namespace."""

from typing import Any

from app.v3.coordinator_transport_schema import (
    MAX_BUNDLE_BYTES,
    _events,
    _snapshots,
    digest,
    reference,
)
from app.v3.relocation_models import RELOCATION_VERSION
from app.v3.relocation_run_schema import PUBLICATION_VERSION, TRANSPORT_VERSION

MANIFEST_FIELDS = frozenset(
    {
        "transport_version",
        "schema_version",
        "engine_version",
        "run_id",
        "input_hash",
        "common_input_hash",
        "registry_common_hash",
        "inputs",
        "catalog",
        "event_chunks",
        "snapshot_chunks",
    }
)


def validate_manifest(value: Any) -> list[dict[str, Any]]:
    if type(value) is not dict or value.keys() != MANIFEST_FIELDS:
        raise ValueError("Relocation manifest has unknown or missing fields")
    versions = ("transport_version", "schema_version", "engine_version")
    expected = (TRANSPORT_VERSION, PUBLICATION_VERSION, RELOCATION_VERSION)
    if (
        any(type(value[k]) is not str for k in versions)
        or tuple(value[k] for k in versions) != expected
    ):
        raise ValueError("Relocation manifest namespace differs")
    for key in ("run_id", "input_hash", "common_input_hash", "registry_common_hash"):
        digest(value[key])
    refs = [reference(value[key], set()) for key in ("inputs", "catalog")]
    if [r["path"] for r in refs] != ["inputs.json", "catalog.json"]:
        raise ValueError("Relocation input/catalog paths differ from their exact roles")
    refs += _events(value["event_chunks"]) + _snapshots(value["snapshot_chunks"])
    if len({r["path"] for r in refs}) != len(refs):
        raise ValueError("Relocation manifest aliases different physical file roles")
    if sum(r["bytes"] for r in refs) > MAX_BUNDLE_BYTES:
        raise ValueError("Relocation bundle exceeds its explicit aggregate byte bound")
    return refs
