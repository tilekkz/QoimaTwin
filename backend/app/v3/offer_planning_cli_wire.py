"""Manifest semantic identity excludes separately hashed timing observations."""

from hashlib import sha256
from typing import Any

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.forecast_placement_models import ForecastPlacementDecision
from app.v3.offer_planning_cli_models import VERSION, versions
from app.v3.offer_planning_cli_storage import descriptor


def producer_bytes(decision: ForecastPlacementDecision) -> dict[str, bytes]:
    stock = decision.stock
    projection = stock.projection
    forecast = projection.forecast_bytes
    return {
        "history": canonical_bytes(parse_json(forecast)["history"]),
        "forecast": forecast,
        "projection": projection.frozen_bytes,
        "stock": stock.frozen_bytes,
        "decision": decision.frozen_bytes,
    }


def planning_status(decision: ForecastPlacementDecision) -> str:
    if decision.selected is not None:
        return "planned"
    if decision.evaluations and all(e.status == "infeasible" for e in decision.evaluations):
        return "infeasible"
    return "no-op"


def semantic_record(decision: ForecastPlacementDecision, request: bytes) -> dict[str, Any]:
    return {
        "request": descriptor("request.json", request),
        "artifacts": {
            name: descriptor(name + ".json", raw) for name, raw in producer_bytes(decision).items()
        },
        "producer_versions": versions(),
        "plan_id": decision.input_hash,
        "status": planning_status(decision),
        "selection_reason": decision.selection_reason,
        "unallocated_offers": sum(
            row.status == "unallocated" for row in decision.stock.allocations
        ),
        "engine_calls": 0,
        "operational_admission": False,
        "actual_test_stream": False,
        "full_n1_acceptance": False,
    }


def manifest_record(
    decision: ForecastPlacementDecision,
    request: bytes,
    observations: bytes,
) -> dict[str, Any]:
    semantic = semantic_record(decision, request)
    identity = {"version": VERSION, "semantic": semantic}
    return {
        **identity,
        "semantic_bundle_id": sha256(canonical_bytes(identity)).hexdigest(),
        "observations": descriptor("observations.json", observations),
    }


def result_record(manifest: dict[str, Any], raw: bytes) -> dict[str, Any]:
    return {
        "status": manifest["semantic"]["status"],
        "plan_id": manifest["semantic"]["plan_id"],
        "semantic_bundle_id": manifest["semantic_bundle_id"],
        "manifest_sha256": sha256(raw).hexdigest(),
        "selection_reason": manifest["semantic"]["selection_reason"],
        "unallocated_offers": manifest["semantic"]["unallocated_offers"],
        "engine_calls": 0,
        "operational_admission": False,
        "actual_test_stream": False,
        "full_n1_acceptance": False,
    }
