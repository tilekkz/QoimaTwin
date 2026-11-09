"""Reconstruct forecast projection and pinned original stock at every public boundary."""

from dataclasses import replace
from hashlib import sha256

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.adaptation_authority import require_same_authority
from app.v3.forecast_stock_models import POLICY, SCOPE, VERSION, ForecastBoundStock
from app.v3.forecast_stock_source import _original_stock
from app.v3.forecast_stock_wire import _record
from app.v3.offer_projection_inputs import load_offer_projection, verify_offer_projection
from app.v3.offer_projection_models import OfferProjectionInputs
from app.v3.outbound_stock_allocation import _allocate_verified_offers
from app.v3.outbound_stock_wire import stock_hash
from app.v3.workload_policy import fields


def _bind_verified(projection: OfferProjectionInputs) -> ForecastBoundStock:
    original, placements = _original_stock(projection)
    rows = _allocate_verified_offers(projection.offers.jobs, original, ())
    value = ForecastBoundStock(
        projection, original, (), placements, rows, stock_hash(original), b"", ""
    )
    raw = canonical_bytes(_record(value))
    return replace(value, frozen_bytes=raw, input_hash=sha256(raw).hexdigest())


def bind_forecast_stock(projection: OfferProjectionInputs) -> ForecastBoundStock:
    return _bind_verified(verify_offer_projection(projection))


def load_forecast_stock(raw: bytes) -> ForecastBoundStock:
    if type(raw) is not bytes:
        raise ValueError("EXACT_FORECAST_STOCK_BYTES_REQUIRED")
    value = fields(
        parse_json(raw),
        {
            "schema_version",
            "scope",
            "allocation_policy",
            "forecast_id",
            "projection_id",
            "projection",
            "original_stock",
            "declared_receipts",
            "initial_placements",
            "allocations",
            "source_stock_hash",
            "operational_admission",
            "full_n1_acceptance",
            "actual_test_stream",
        },
    )
    if canonical_bytes(value) != raw:
        raise ValueError("CANONICAL_FORECAST_STOCK_BYTES_REQUIRED")
    if (value["schema_version"], value["scope"], value["allocation_policy"]) != (
        VERSION,
        SCOPE,
        POLICY,
    ):
        raise ValueError("UNSUPPORTED_FORECAST_STOCK_VERSION")
    projection = load_offer_projection(canonical_bytes(value["projection"]))
    expected = _bind_verified(projection)
    if expected.frozen_bytes != raw:
        raise ValueError("FORECAST_STOCK_DIFFERS_FROM_RECONSTRUCTED_AUTHORITY")
    return expected


def verify_forecast_stock(value: ForecastBoundStock) -> ForecastBoundStock:
    if type(value) is not ForecastBoundStock:
        raise ValueError("EXACT_FORECAST_BOUND_STOCK_REQUIRED")
    expected = load_forecast_stock(value.frozen_bytes)
    require_same_authority(value, expected)
    return expected
