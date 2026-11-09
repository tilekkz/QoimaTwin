"""Separate forecast/projection identities and all finite-stock allocation rows."""

from dataclasses import asdict
from typing import Any

from app.storage.canonical_json import parse_json
from app.v3.forecast_stock_models import POLICY, SCOPE, VERSION, ForecastBoundStock
from app.v3.outbound_stock_wire import allocation_dict, stock_dict


def _record(value: ForecastBoundStock) -> dict[str, Any]:
    return {
        "schema_version": VERSION,
        "scope": SCOPE,
        "allocation_policy": POLICY,
        "forecast_id": value.projection.forecast_id,
        "projection_id": value.projection.input_hash,
        "projection": parse_json(value.projection.frozen_bytes),
        "original_stock": [stock_dict(hu) for hu in value.original_stock],
        "declared_receipts": [stock_dict(hu) for hu in value.declared_receipts],
        "initial_placements": [asdict(place) for place in value.initial_placements],
        "allocations": [allocation_dict(row) for row in value.allocations],
        "source_stock_hash": value.source_stock_hash,
        "operational_admission": False,
        "full_n1_acceptance": False,
        "actual_test_stream": False,
    }
