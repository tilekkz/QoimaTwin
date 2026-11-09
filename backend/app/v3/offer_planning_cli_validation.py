"""Full byte inventory and one authoritative decision reconstruction, without an engine."""

import math
from dataclasses import replace
from pathlib import Path
from typing import Any

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.flow_profile_wire import record
from app.v3.forecast_placement_decision import load_forecast_placement_decision
from app.v3.forecast_placement_models import ForecastPlacementDecision
from app.v3.offer_history_choices import choices_record
from app.v3.offer_planning_cli_choices import decode_request_choices
from app.v3.offer_planning_cli_models import RAW_NAMES, REQUEST_FIELDS, SEMANTIC_FIELDS, STAGES
from app.v3.offer_planning_cli_storage import (
    canonical_document,
    checked_file,
    closed_inventory,
    read_regular,
    request_record,
)
from app.v3.offer_planning_cli_wire import manifest_record, producer_bytes, result_record
from app.v3.outbound_placement_wire import record as placement_record
from app.v3.workload_policy import fields


def _observations(raw: bytes) -> None:
    value = fields(
        canonical_document(raw),
        {"version", "planning_elapsed_s", "forecast_cpu", "benchmark_claim"},
    )
    cpu = fields(value["forecast_cpu"], {"total_s", "validation_s", "final_fit_s"})
    for number in (value["planning_elapsed_s"], *cpu.values()):
        if type(number) is not float or not math.isfinite(number) or number < 0:
            raise ValueError("Timing observations require finite nonnegative floats")
    if (
        value["version"] != "qoima-offer-planning-observations-0.1.0"
        or value["benchmark_claim"] is not False
    ):
        raise ValueError("Unsupported planning observations")


def _choices(decision: ForecastPlacementDecision, raw: dict[str, bytes], model: str) -> None:
    choices = decode_request_choices(raw)
    forecast = parse_json(decision.stock.projection.forecast_bytes)
    history = forecast["history"]
    if (
        history["raw_history_utf8"].encode("utf-8") != raw["history.csv"]
        or forecast["model"] != model
    ):
        raise ValueError("Raw history or model differs from authenticated decision")
    projection = replace(
        choices.projection,
        port_mix=tuple(
            sorted(choices.projection.port_mix, key=lambda row: (row.sku_id, row.port_id))
        ),
    )
    pairs = (
        (choices_record(choices.history), history["choices"]),
        (record(projection), record(decision.stock.projection.choices)),
        (placement_record(choices.placement), placement_record(decision.choices)),
    )
    if any(canonical_bytes(a) != canonical_bytes(b) for a, b in pairs):
        raise ValueError("Explicit request choices differ from authenticated decision")


def validate_offer_plan(root: Path) -> dict[str, Any]:
    closed_inventory(root)
    wire = read_regular(root / "manifest.json")
    manifest = fields(
        canonical_document(wire), {"version", "semantic", "semantic_bundle_id", "observations"}
    )
    semantic = fields(manifest["semantic"], SEMANTIC_FIELDS)
    stages = fields(semantic["artifacts"], set(STAGES))
    artifacts = {name: checked_file(root, name + ".json", stages[name]) for name in STAGES}
    request = checked_file(root, "request.json", semantic["request"])
    value = fields(canonical_document(request), REQUEST_FIELDS)
    raw = {name: read_regular(root / "raw" / name) for name in RAW_NAMES}
    if request != canonical_bytes(request_record(value["model"], raw)):
        raise ValueError("Frozen planning request or raw input hashes differ")
    observations = checked_file(root, "observations.json", manifest["observations"])
    _observations(observations)
    decision = load_forecast_placement_decision(artifacts["decision"])
    if artifacts != producer_bytes(decision):
        raise ValueError("Saved producer bytes differ from authenticated nested chain")
    _choices(decision, raw, value["model"])
    if wire != canonical_bytes(manifest_record(decision, request, observations)):
        raise ValueError("Planning manifest differs from reconstructed authority")
    result = result_record(manifest, wire)
    return {
        **result,
        "planning_status": result["status"],
        "status": "passed",
        "validation_scope": "data_only_planning_bundle",
    }
