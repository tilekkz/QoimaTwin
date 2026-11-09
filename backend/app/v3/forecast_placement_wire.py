"""Separate closed namespace binds complete forecast stock, choices and recomputed costs."""

from typing import Any

from app.storage.canonical_json import parse_json
from app.v3.forecast_placement_models import SCOPE, VERSION, ForecastPlacementDecision
from app.v3.outbound_placement_models import SELECTION_POLICY
from app.v3.outbound_placement_wire import record


def decision_record(value: ForecastPlacementDecision) -> dict[str, Any]:
    return {
        "schema_version": VERSION,
        "scope": SCOPE,
        "selection_policy": SELECTION_POLICY,
        "forecast_id": value.forecast_id,
        "projection_id": value.projection_id,
        "stock_input_hash": value.stock_input_hash,
        "stock_inputs": parse_json(value.stock.frozen_bytes),
        "choices": record(value.choices),
        "evaluations": record(value.evaluations),
        "selected": record(value.selected),
        "no_op": value.no_op,
        "selection_reason": value.selection_reason,
        "placements": record(value.placements),
        "operational_admission": False,
        "actual_test_stream": False,
        "full_n1_acceptance": False,
    }
