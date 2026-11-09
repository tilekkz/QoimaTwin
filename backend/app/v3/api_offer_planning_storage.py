"""Closed CAS publication and raw guards; typed producer validation stays in the worker."""

from pathlib import Path
from typing import Any

from app.storage.artifacts import ArtifactCorruption, ArtifactStore, require_identifier
from app.storage.canonical_json import canonical_bytes
from app.v3.api_offer_planning_inputs import DOMAIN, UnknownOfferPlan, load_request, public_id
from app.v3.offer_planning_cli_models import RAW_NAMES, STAGES
from app.v3.offer_planning_cli_storage import descriptor, put, read_regular, request_record
from app.v3.workload_policy import fields

NAMES = tuple(
    sorted(
        [
            *("raw/" + name for name in RAW_NAMES),
            *(name + ".json" for name in STAGES),
            "request.json",
            "observations.json",
            "manifest.json",
        ]
    )
)


def _bound_request(store: ArtifactStore, request_id: str, raw: dict[str, bytes]) -> None:
    request, original = load_request(store, request_id)
    if any(raw["raw/" + name] != original[name] for name in RAW_NAMES):
        raise ArtifactCorruption("Published raw choices differ from immutable request")
    if raw["request.json"] != canonical_bytes(request_record(request["model"], original)):
        raise ArtifactCorruption("CLI request differs from API declarations")


def known(store: ArtifactStore, identifier: str) -> dict[str, Any]:
    value = store.read_reference("runs", identifier)
    if value is None:
        raise UnknownOfferPlan("Unknown V3 offer planning result")
    try:
        index = fields(value, {"domain", "planning_id", "request_id", "files", "result"})
        if index["domain"] != DOMAIN or index["planning_id"] != identifier:
            raise ValueError("Wrong offer planning namespace")
        if public_id(require_identifier(index["request_id"])) != identifier:
            raise ValueError("Request/public identity differs")
        return index
    except (ValueError, TypeError, KeyError) as exc:
        raise ArtifactCorruption("Offer planning publication identity is invalid") from exc


def checked(store: ArtifactStore, identifier: str) -> tuple[dict[str, Any], dict[str, bytes]]:
    index = known(store, identifier)
    try:
        rows = index["files"]
        if type(rows) is not list or len(rows) != len(NAMES):
            raise ValueError("Closed offer planning inventory required")
        raw = {
            name: store.read_bytes("run_files", row["sha256"])
            for name, row in zip(NAMES, rows, strict=True)
        }
        expected = [descriptor(name, raw[name]) for name in NAMES]
        if canonical_bytes(rows) != canonical_bytes(expected):
            raise ValueError("Offer planning file descriptors differ")
        _bound_request(store, index["request_id"], raw)
        return index, raw
    except (ValueError, TypeError, KeyError, OSError) as exc:
        raise ArtifactCorruption("Offer planning saved bytes are invalid") from exc


def response(index: dict[str, Any]) -> dict[str, Any]:
    return {
        **_public_result(index["result"]),
        "domain": DOMAIN,
        "planning_id": index["planning_id"],
        "request_id": index["request_id"],
        "files": index["files"],
    }


def _public_result(value: object) -> dict[str, Any]:
    try:
        row = fields(
            value,
            {
                "status",
                "plan_id",
                "semantic_bundle_id",
                "manifest_sha256",
                "selection_reason",
                "unallocated_offers",
                "engine_calls",
                "operational_admission",
                "actual_test_stream",
                "full_n1_acceptance",
            },
        )
        if type(row["status"]) is not str or row["status"] not in {
            "planned",
            "no-op",
            "infeasible",
        }:
            raise ValueError("Unknown planning status")
        for key in ("plan_id", "semantic_bundle_id", "manifest_sha256"):
            require_identifier(row[key])
        if type(row["selection_reason"]) is not str or not row["selection_reason"]:
            raise ValueError("Selection reason required")
        if type(row["unallocated_offers"]) is not int or row["unallocated_offers"] < 0:
            raise ValueError("Exact nonnegative shortage count required")
        if type(row["engine_calls"]) is not int or row["engine_calls"] != 0:
            raise ValueError("Planning cannot claim engine execution")
        if any(
            row[key] is not False
            for key in ("operational_admission", "actual_test_stream", "full_n1_acceptance")
        ):
            raise ValueError("Unsupported planning claim")
        return row
    except (ValueError, TypeError, KeyError) as exc:
        raise ArtifactCorruption("Offer planning public result is invalid") from exc


def verified_response(
    store: ArtifactStore, result: dict[str, Any], identifier: str
) -> dict[str, Any]:
    index, _ = checked(store, identifier)
    expected = response(index)
    if canonical_bytes(result) != canonical_bytes(expected):
        raise ArtifactCorruption("Cached offer planning result differs from saved publication")
    return expected


def restored(root: Path, raw: dict[str, bytes]) -> None:
    for name in NAMES:
        put(root, name, raw[name])


def publish(
    store: ArtifactStore, request_id: str, root: Path, result: dict[str, Any]
) -> dict[str, Any]:
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if actual != set(NAMES):
        raise ArtifactCorruption("Producer output inventory differs")
    raw = {name: read_regular(root / name) for name in NAMES}
    _bound_request(store, request_id, raw)
    result = _public_result(result)
    rows = [
        {"path": name, "bytes": len(raw[name]), "sha256": store.put_bytes("run_files", raw[name])}
        for name in NAMES
    ]
    identifier = public_id(request_id)
    index = {
        "domain": DOMAIN,
        "planning_id": identifier,
        "request_id": request_id,
        "files": rows,
        "result": result,
    }
    store.publish_reference("runs", identifier, index)
    return verified_response(store, response(index), identifier)
