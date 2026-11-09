"""Closed data-only C bundle descriptors with bounded local file authority."""

from pathlib import PurePosixPath
from typing import Any

from app.v3.coordinator_models import COORDINATOR_VERSION
from app.v3.coordinator_run_schema import PUBLICATION_VERSION, TRANSPORT_VERSION

EVENT_CHUNK_TICKS = 60_000_000
MAX_FILE_BYTES = 128 * 1024 * 1024
MAX_BUNDLE_BYTES = 1024 * 1024 * 1024
BASE_REF = {"path", "bytes", "sha256"}
MANIFEST_FIELDS = {
    "transport_version",
    "schema_version",
    "engine_version",
    "run_id",
    "input_hash",
    "registry_common_hash",
    "inputs",
    "catalog",
    "event_chunks",
    "snapshot_chunks",
}


def reference(value: Any, extra: set[str]) -> dict[str, Any]:
    if type(value) is not dict or value.keys() != BASE_REF | extra:
        raise ValueError("Coordinator descriptor has unknown or missing fields")
    path = value["path"]
    if (
        type(path) is not str
        or not path
        or "\\" in path
        or PurePosixPath(path).is_absolute()
        or ":" in path
        or any(part in {"", ".", ".."} for part in path.split("/"))
    ):
        raise ValueError("Coordinator file descriptor requires a safe relative path")
    if type(value["bytes"]) is not int or not 0 < value["bytes"] <= MAX_FILE_BYTES:
        raise ValueError("Coordinator descriptor exceeds the explicit file byte bound")
    digest(value["sha256"])
    return value


def digest(value: Any) -> None:
    if (
        type(value) is not str
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ValueError("Coordinator descriptor requires an exact lowercase SHA256")


def validate_manifest(value: Any) -> list[dict[str, Any]]:
    if type(value) is not dict or value.keys() != MANIFEST_FIELDS:
        raise ValueError("Coordinator manifest has unknown or missing fields")
    if (value["transport_version"], value["schema_version"], value["engine_version"]) != (
        TRANSPORT_VERSION,
        PUBLICATION_VERSION,
        COORDINATOR_VERSION,
    ):
        raise ValueError("Coordinator manifest namespace differs")
    for key in ("run_id", "input_hash", "registry_common_hash"):
        digest(value[key])
    refs = [reference(value[key], set()) for key in ("inputs", "catalog")]
    if [r["path"] for r in refs] != ["inputs.json", "catalog.json"]:
        raise ValueError("Coordinator input/catalog paths differ from their exact roles")
    refs += _events(value["event_chunks"]) + _snapshots(value["snapshot_chunks"])
    if len({r["path"] for r in refs}) != len(refs):
        raise ValueError("Coordinator manifest aliases different physical file roles")
    if sum(r["bytes"] for r in refs) > MAX_BUNDLE_BYTES:
        raise ValueError("Coordinator bundle exceeds its explicit aggregate byte bound")
    return refs


def _events(values: Any) -> list[dict[str, Any]]:
    if type(values) is not list:
        raise ValueError("Coordinator event chunk references require an array")
    refs, previous, seq = [], -1, 0
    for value in values:
        ref = reference(value, {"start_tick", "end_tick", "first_seq", "last_seq"})
        if any(
            type(ref[k]) is not int or ref[k] < 0
            for k in ("start_tick", "end_tick", "first_seq", "last_seq")
        ):
            raise ValueError("Coordinator event chunk boundaries require exact integers")
        start, end = ref["start_tick"], ref["end_tick"]
        if start <= previous or start % EVENT_CHUNK_TICKS or end != start + EVENT_CHUNK_TICKS:
            raise ValueError("Coordinator event chunks do not follow exact half-open source ticks")
        if ref["first_seq"] != seq or ref["last_seq"] < seq:
            raise ValueError("Coordinator event chunk sequence is not contiguous")
        previous, seq = start, ref["last_seq"] + 1
        refs.append(ref)
    return refs


def _snapshots(values: Any) -> list[dict[str, Any]]:
    if type(values) is not list or not values:
        raise ValueError("Coordinator captures require a nonempty descriptor array")
    refs, previous, counts = [], -1, {"at_horizon": 0, "at_end": 0}
    for value in values:
        ref = reference(value, {"tick", "last_seq", "roles"})
        if type(ref["tick"]) is not int or ref["tick"] <= previous:
            raise ValueError("Coordinator capture ticks must be strictly increasing")
        if type(ref["last_seq"]) is not int or ref["last_seq"] < -1:
            raise ValueError("Coordinator capture watermark requires an exact observed sequence")
        roles = ref["roles"]
        allowed = ("checkpoint", "at_horizon", "at_end")
        if type(roles) is not list or not roles or roles != [r for r in allowed if r in roles]:
            raise ValueError("Coordinator capture roles must be unique and canonically ordered")
        for role in counts:
            counts[role] += int(role in roles)
        previous = ref["tick"]
        refs.append(ref)
    if any(count != 1 for count in counts.values()):
        raise ValueError("Coordinator bundle requires exactly one H/end captured role")
    return refs
