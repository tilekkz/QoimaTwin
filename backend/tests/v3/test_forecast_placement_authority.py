"""Forecast decisions cannot impersonate C11, and metadata cannot replace fresh authority."""

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.forecast_placement_decision import (
    load_forecast_placement_decision,
    prepare_forecast_placement_decision,
    verify_forecast_placement_decision,
)
from app.v3.forecast_placement_models import ForecastPlacementDecision
from app.v3.forecast_stock_models import ForecastBoundStock
from app.v3.outbound_placement_decision import (
    load_placement_decision,
    prepare_placement_decision,
    verify_placement_decision,
)
from app.v3.outbound_stock_models import BoundOutboundStock
from tests.v3.test_forecast_placement_fixtures import choices, stock
from tests.v3.test_outbound_placement_inputs import stock as legacy_stock

__all__ = ["legacy_stock", "stock"]


@pytest.fixture(scope="module")
def bound(stock: ForecastBoundStock) -> ForecastPlacementDecision:
    return prepare_forecast_placement_decision(stock, choices())


def test_public_load_and_verify_return_fresh_source_bound_result(
    bound: ForecastPlacementDecision,
) -> None:
    fresh = verify_forecast_placement_decision(bound)
    assert fresh == bound == load_forecast_placement_decision(bound.frozen_bytes)
    assert fresh is not bound and fresh.stock is not bound.stock
    assert fresh.stock.projection.source is not bound.stock.projection.source


def test_c11_and_forecast_namespaces_reject_each_other(
    bound: ForecastPlacementDecision,
    legacy_stock: BoundOutboundStock,
) -> None:
    old = prepare_placement_decision(legacy_stock, choices())
    for reader, raw in (
        (load_placement_decision, bound.frozen_bytes),
        (load_forecast_placement_decision, old.frozen_bytes),
    ):
        with pytest.raises(ValueError):
            reader(raw)
    with pytest.raises(ValueError):
        prepare_forecast_placement_decision(legacy_stock, choices())  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        prepare_placement_decision(bound.stock, choices())  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        verify_placement_decision(bound)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        verify_forecast_placement_decision(old)  # type: ignore[arg-type]


@pytest.mark.parametrize("field", ["forecast_id", "projection_id", "stock_input_hash"])
def test_rehashed_join_identity_rejects(bound: ForecastPlacementDecision, field: str) -> None:
    wire = parse_json(bound.frozen_bytes)
    wire[field] = "f" * 64
    with pytest.raises(ValueError):
        load_forecast_placement_decision(canonical_bytes(wire))


def test_rehashed_placement_stream_and_extra_actual_authority_reject(
    bound: ForecastPlacementDecision,
) -> None:
    wire = parse_json(bound.frozen_bytes)
    wire["placements"][0]["slot_id"] = "invented"
    with pytest.raises(ValueError):
        load_forecast_placement_decision(canonical_bytes(wire))
    wire = parse_json(bound.frozen_bytes)
    wire["actual_workload"] = []
    with pytest.raises(ValueError):
        load_forecast_placement_decision(canonical_bytes(wire))


def test_retained_equal_aliases_and_changed_allocations_fail_closed(
    bound: ForecastPlacementDecision,
) -> None:
    alias: Any = 1
    with pytest.raises(ValueError):
        verify_forecast_placement_decision(replace(bound, no_op=alias))
    stock = replace(bound.stock, allocations=bound.stock.allocations[:-1])
    with pytest.raises(ValueError):
        prepare_forecast_placement_decision(stock, choices())
    with pytest.raises(ValueError):
        verify_forecast_placement_decision(replace(bound, placements=list(bound.placements)))  # type: ignore[arg-type]


def test_fresh_raw_source_is_reopened(
    bound: ForecastPlacementDecision, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = Path.read_bytes

    def changed(path: Path) -> bytes:
        value = original(path)
        return value + b" " if path.name == "cargo-catalog-v3.json" else value

    monkeypatch.setattr(Path, "read_bytes", changed)
    with pytest.raises(ValueError):
        verify_forecast_placement_decision(bound)
