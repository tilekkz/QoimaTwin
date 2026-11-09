"""Fresh forecast-v2 projection and finite original stock; no execution grant."""

from dataclasses import replace
from fractions import Fraction as F
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.forecast_stock_binding import (
    bind_forecast_stock,
    load_forecast_stock,
    verify_forecast_stock,
)
from app.v3.forecast_stock_models import ForecastBoundStock
from app.v3.offer_forecast import fit_offer_forecast
from app.v3.offer_history import compile_offer_history
from app.v3.offer_projection_inputs import compile_offer_projection
from app.v3.offer_projection_models import OfferProjectionChoices
from app.v3.workload_models import WorkloadPolicy
from tests.v3.test_offer_history_fixtures import choices, history_bytes


@pytest.fixture(scope="module")
def bound() -> ForecastBoundStock:
    raw = history_bytes(1, 0).replace(b",DEMO_172,0\n", b",DEMO_172,1\n")
    forecast = fit_offer_forecast(compile_offer_history(raw, choices()), "mean28")
    policy = OfferProjectionChoices(WorkloadPolicy(20, 0, 20, "normal"), "source_c10", ())
    return bind_forecast_stock(compile_offer_projection(forecast, policy))


def test_source_bind_preserves_all_stock_offers_and_visible_shortages(
    bound: ForecastBoundStock,
) -> None:
    assert len(bound.original_stock) == len(bound.initial_placements) == 530
    assert sum(hu.quantity_units for hu in bound.original_stock) == 12256
    assert sum((hu.gross_mass_kg for hu in bound.original_stock), F(0)) == F("9403.85")
    assert bound.declared_receipts == ()
    assert tuple(row.offer for row in bound.allocations) == bound.projection.offers.jobs
    assert len(bound.allocations) == 20
    assert sum(row.status == "original_bound" for row in bound.allocations) == 5
    assert sum(row.reason == "DECLARED_STOCK_EXHAUSTED" for row in bound.allocations) == 15
    allocated = [row.hu.hu_id for row in bound.allocations if row.hu is not None]
    assert len(allocated) == len(set(allocated)) == 5
    assert any(row.offer.port_id == "OUT_E_B2B" for row in bound.allocations)
    assert not bound.operational_admission and not bound.full_n1_acceptance
    assert not bound.actual_test_stream
    wire = parse_json(bound.frozen_bytes)
    assert wire["forecast_id"] == bound.projection.forecast_id
    assert wire["projection_id"] == bound.projection.input_hash


def test_load_verify_reconstruct_fresh_source_and_same_bytes(bound: ForecastBoundStock) -> None:
    fresh = verify_forecast_stock(bound)
    assert fresh == load_forecast_stock(bound.frozen_bytes) == bound
    assert fresh is not bound and fresh.projection is not bound.projection
    assert bind_forecast_stock(bound.projection).frozen_bytes == bound.frozen_bytes


def test_explicit_zero_budget_preserves_all_original_stock() -> None:
    history = compile_offer_history(history_bytes(0, 0), choices())
    forecast = fit_offer_forecast(history, "mean28")
    policy = OfferProjectionChoices(WorkloadPolicy(20, 0, 0, "normal"), "source_c10", ())
    stock = bind_forecast_stock(compile_offer_projection(forecast, policy))
    assert stock.allocations == ()
    assert stock.declared_receipts == ()
    assert len(stock.original_stock) == len(stock.initial_placements) == 530


@pytest.mark.parametrize(
    "mutation", ["clone", "drop", "receipt", "arrival", "stock", "placement", "id"]
)
def test_rehashed_wire_does_not_authorize_changed_stock_or_offers(
    bound: ForecastBoundStock,
    mutation: str,
) -> None:
    value = parse_json(bound.frozen_bytes)
    if mutation == "clone":
        value["allocations"][1]["hu"] = value["allocations"][0]["hu"]
    elif mutation == "drop":
        value["allocations"].pop()
    elif mutation == "receipt":
        value["declared_receipts"] = [value["original_stock"][0]]
    elif mutation == "arrival":
        value["allocations"][0]["offer"]["arrival_tick"] += 1
    elif mutation == "stock":
        value["original_stock"][0]["lot_id"] = "invented-lot"
    elif mutation == "placement":
        value["initial_placements"][0]["slot_id"] = "invented-slot"
    else:
        value["forecast_id"] = "f" * 64
    raw = canonical_bytes(value)
    with pytest.raises(ValueError):
        verify_forecast_stock(replace(bound, frozen_bytes=raw, input_hash=sha256(raw).hexdigest()))


@pytest.mark.parametrize("mutation", ["mass", "tick", "placement", "receipts", "hash"])
def test_retained_values_require_exact_types_and_authority(
    bound: ForecastBoundStock,
    mutation: str,
) -> None:
    if mutation == "mass":
        alias: Any = float(bound.original_stock[0].gross_mass_kg)
        hu = replace(bound.original_stock[0], gross_mass_kg=alias)
        forged = replace(bound, original_stock=(hu, *bound.original_stock[1:]))
    elif mutation == "tick":
        row = bound.allocations[0]
        forged_row = replace(row, offer=replace(row.offer, arrival_tick=False))
        forged = replace(bound, allocations=(forged_row, *bound.allocations[1:]))
    elif mutation == "placement":
        placement = replace(bound.initial_placements[0], module_id="invented-module")
        forged = replace(bound, initial_placements=(placement, *bound.initial_placements[1:]))
    elif mutation == "receipts":
        empty_list: Any = []
        forged = replace(bound, declared_receipts=empty_list)
    else:
        forged = replace(bound, source_stock_hash="0" * 64)
    with pytest.raises(ValueError):
        verify_forecast_stock(forged)


def test_projection_changes_rejected_before_stock_binding(bound: ForecastBoundStock) -> None:
    offers = replace(bound.projection.offers, jobs=bound.projection.offers.jobs * 2)
    with pytest.raises(ValueError):
        bind_forecast_stock(replace(bound.projection, offers=offers))
    with pytest.raises(ValueError):
        bind_forecast_stock(replace(bound.projection, initial_hus=()))


def test_stock_reopens_pinned_raw_source(
    bound: ForecastBoundStock, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = Path.read_bytes

    def changed(path: Path) -> bytes:
        raw = original(path)
        return raw + b" " if path.name == "baseline-assignment-v3.json" else raw

    monkeypatch.setattr(Path, "read_bytes", changed)
    with pytest.raises(ValueError):
        verify_forecast_stock(bound)


@pytest.mark.parametrize("raw", [None, "{}", bytearray(b"{}"), b"[]", b"{}"])
def test_exact_wire_type_and_shape_required(raw: Any) -> None:
    with pytest.raises(ValueError):
        load_forecast_stock(raw)


def test_old_namespace_and_noncanonical_wire_rejected(bound: ForecastBoundStock) -> None:
    value = parse_json(bound.frozen_bytes)
    value["schema_version"] = "qoima-n1-outbound-stock-0.1.0"
    with pytest.raises(ValueError):
        load_forecast_stock(canonical_bytes(value))
    with pytest.raises(ValueError):
        load_forecast_stock(bound.frozen_bytes + b"\n")
