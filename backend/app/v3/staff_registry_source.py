"""Verify only the three pinned staffing sources; no caller-supplied hash is authority."""

import hashlib
from pathlib import Path
from typing import Any, cast

from app.storage.canonical_json import parse_json
from app.v3.conveyor_source import RAW_BYTES, RAW_SHA256, SOURCE_PATH
from app.v3.input_json import PREFIX
from app.v3.input_pin import PROVENANCE_SHA256, SOURCE_REVISION
from app.v3.staff_registry_models import StaffSource, StaffStation
from app.v3.staff_registry_source_values import positions, source_stations
from app.v3.staff_registry_values import Role


def _pinned_document(root: Path, name: str) -> tuple[dict[str, Any], tuple[str, str, int]]:
    provenance = (root / "provenance.json").read_bytes()
    if hashlib.sha256(provenance).hexdigest() != PROVENANCE_SHA256:
        raise ValueError("STAFF_SOURCE_PROVENANCE_MISMATCH")
    rows = parse_json(provenance)["sources"]
    row = next(item for item in rows if item["path"] == PREFIX + name)
    raw = (root / row["path"]).read_bytes()
    if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["raw_sha256"]:
        raise ValueError("STAFF_SOURCE_BYTES_MISMATCH")
    return parse_json(raw), (row["path"], row["raw_sha256"], row["bytes"])


def _conveyor_document(root: Path) -> dict[str, Any]:
    raw = (root / "conveyor-v3.json").read_bytes()
    if len(raw) != RAW_BYTES or hashlib.sha256(raw).hexdigest() != RAW_SHA256:
        raise ValueError("STAFF_CONVEYOR_BYTES_MISMATCH")
    return cast(dict[str, Any], parse_json(raw))


def load_staff_source(data_root: Path | None = None) -> StaffSource:
    """Read and rehash raw authority on every call, never retain unverified cached facts."""
    root = data_root or Path(__file__).resolve().parents[2] / "data"
    try:
        return _load_source(root)
    except OSError as exc:
        raise ValueError("STAFF_SOURCE_UNAVAILABLE") from exc


def _load_source(root: Path) -> StaffSource:
    policy, policy_pin = _pinned_document(root / "v3-proposal", "port-resource-policy-v3.json")
    links, links_pin = _pinned_document(root / "v3-proposal", "layout-links-v3.json")
    conveyor = _conveyor_document(root / "v3-conveyor-proposal")
    stations = source_stations(conveyor, positions(links))
    pools = {p["pool_id"]: tuple(sorted(p["actor_ids"])) for p in policy["pools"]}
    roles: dict[str, Role] = {
        "P": "pick",
        "K": "pack",
        "R": "receive",
        "S": "ship",
        "F": "forklift",
    }
    return StaffSource(
        SOURCE_REVISION,
        tuple(sorted((policy_pin, links_pin, (SOURCE_PATH, RAW_SHA256, RAW_BYTES)))),
        tuple(sorted(policy["actor_ids"])),
        tuple(sorted((actor, roles[actor[0]]) for actor in policy["actor_ids"])),
        pools["RECEIVERS_SHARED"],
        pools["SHIPPERS_SHARED"],
        tuple(sorted((p["actor_id"], p["vehicle_id"]) for p in policy["forklift_pairs"])),
        stations,
    )


def source_record(source: StaffSource) -> dict[str, Any]:
    return {
        "revision": source.revision,
        "fingerprints": source.fingerprints,
        "actor_ids": source.actor_ids,
        "primary_roles": source.primary_roles,
        "receivers": source.receivers,
        "shippers": source.shippers,
        "forklift_pairs": source.forklift_pairs,
        "stations": [station_record(s) for s in source.stations],
    }


def station_record(station: StaffStation) -> dict[str, Any]:
    def point(value: tuple[Any, ...]) -> list[dict[str, int]]:
        return [{"numerator": v.numerator, "denominator": v.denominator} for v in value]

    return {
        "station_id": station.station_id,
        "service_node_id": station.service_node_id,
        "worker_position": point(station.worker_position),
        "work_node_id": station.work_node_id,
        "work_position": point(station.work_position),
        "spur_resource_id": station.spur_resource_id,
    }
