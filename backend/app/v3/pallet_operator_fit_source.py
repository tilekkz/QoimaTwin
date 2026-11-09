"""Pinned original worker bytes supplement existing immutable pickup authority."""

from dataclasses import replace
from hashlib import sha1, sha256
from pathlib import Path
from typing import Any

from app.storage.canonical_json import parse_json
from app.v3.pallet_operator_fit_models import OperatorFitSource
from app.v3.pallet_outbound_pickup_identity import identity, require
from app.v3.pallet_outbound_pickup_source import (
    document,
    load_pickup_source,
    raw_document,
    verify_pickup_source,
)

WORKER_PATH = "frontend/public/models/v3/worker-base.glb"
WORKER_SHA256 = "c8546473c76f126844b427417db86e65be090fa04ad56c0deb9cb2bda92e73b7"
WORKER_BLOB = "fbdbd430af28390c18724aa61e9c4de0f028276e"
PROVENANCE_SHA256 = "fb6f2174fa9bbb40f8c226b74a872bdad7df00907408c6d240deeaa0a600d99d"
SPEC_PATH = "assets/v3/specs/forklift.dimensions.json"


def forklift_spec(source: OperatorFitSource) -> dict[str, Any]:
    raw = raw_document(source.pickup, "v3-mesh-proof-proposal", SPEC_PATH)
    result: dict[str, Any] = parse_json(raw)
    return result


def load_operator_fit_source(data_root: Path, worker_root: Path) -> OperatorFitSource:
    try:
        result = OperatorFitSource(
            load_pickup_source(data_root),
            (worker_root / "worker-base.glb").read_bytes(),
            (worker_root / "provenance.json").read_bytes(),
            "",
        )
    except OSError as error:
        raise ValueError("Operator worker source missing or unreadable") from error
    result = replace(result, source_hash=identity(result))
    verify_operator_fit_source(result)
    return result


def _check_worker_reference(source: OperatorFitSource) -> None:
    spec = forklift_spec(source)
    driver = spec["driver"]
    reference = next(row for row in spec["input_fingerprints"] if row["path"] == WORKER_PATH)
    require(reference["sha256"] == WORKER_SHA256, "Source spec worker fingerprint differs")
    require(
        driver["asset"] == WORKER_PATH
        and driver["worker_geometry_unchanged"] is True
        and driver["worker_scale"] == [1, 1, 1],
        "Unchanged source worker geometry and scale required",
    )
    require(
        spec["staffing"] == "F01/F02 existing typed driver actors are seated clones of "
        "unchanged worker-base at vehicle seat; not two additional people",
        "Source template-to-existing-actor authority differs",
    )


def verify_operator_fit_source(source: OperatorFitSource) -> None:
    require(type(source) is OperatorFitSource, "Exact OperatorFitSource required")
    require(
        type(source.worker_raw) is bytes
        and type(source.provenance_raw) is bytes
        and type(source.source_hash) is str,
        "Exact immutable source fields required",
    )
    verify_pickup_source(source.pickup)
    require(
        sha256(source.provenance_raw).hexdigest() == PROVENANCE_SHA256,
        "Operator worker provenance changed",
    )
    raw = source.worker_raw
    require(
        len(raw) == 181828 and sha256(raw).hexdigest() == WORKER_SHA256,
        "Pinned original worker bytes changed",
    )
    require(
        sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest() == WORKER_BLOB,
        "Pinned worker Git blob ancestry changed",
    )
    _check_worker_reference(source)
    require(
        source.source_hash == identity(replace(source, source_hash="")),
        "Operator source typed identity changed",
    )


def verify_outbound_pair(source: OperatorFitSource, actor: str, vehicle: str) -> str:
    policy = document(source.pickup, "port-resource-policy-v3.json")
    pair = next(p for p in policy["forklift_pairs"] if p["pair_id"] == "OUTBOUND_FORKLIFT_PAIR")
    require(
        (actor, vehicle) == (pair["actor_id"], pair["vehicle_id"]) == ("F02", "FL02"),
        "Actual outbound F02/FL02 pair required",
    )
    require(
        policy["actor_count"] == len(policy["actor_ids"]) == 24
        and actor in policy["actor_ids"]
        and pair["eligible_direction"] == "outbound",
        "Original outbound actor inventory/direction required",
    )
    return "OUTBOUND_FORKLIFT_PAIR"
