"""Independent allocation boundary probes; no warehouse engine or operational grant."""

from dataclasses import replace
from fractions import Fraction as F
from pathlib import Path
from typing import Any

import pytest

from app.storage.canonical_json import canonical_bytes, parse_json, sha256_hex
from app.v3 import forecast_stock_source
from app.v3.forecast_stock_binding import (
    bind_forecast_stock,
    load_forecast_stock,
    verify_forecast_stock,
)
from app.v3.forecast_stock_models import ForecastBoundStock
from app.v3.input_models import V3Bundle
from app.v3.inputs import load_v3_bundle
from app.v3.offer_forecast import fit_offer_forecast
from app.v3.offer_history import compile_offer_history
from app.v3.offer_projection_inputs import compile_offer_projection
from app.v3.offer_projection_models import OfferProjectionChoices
from app.v3.outbound_shift_inputs import compile_outbound_shift
from app.v3.outbound_stock_allocation import allocate_offers, declared_receipts
from app.v3.outbound_stock_binding import (
    bind_outbound_stock,
    load_outbound_stock,
    verify_outbound_stock,
)
from app.v3.outbound_stock_models import BoundOutboundStock
from app.v3.workload_models import WorkloadPolicy
from tests.v3.test_offer_history_fixtures import choices as history_choices
from tests.v3.test_offer_history_fixtures import history_bytes
from tests.v3.test_outbound_stock_fixtures import initial, workload


class StringAlias(str):
    """Equality must not authorize a different retained scalar type."""


@pytest.fixture(scope="module")
def stock() -> ForecastBoundStock:
    history = compile_offer_history(history_bytes(), history_choices())
    forecast = fit_offer_forecast(history, "mean28")
    choices = OfferProjectionChoices(WorkloadPolicy(8_000_000, 0, 8, "normal"), "source_c10", ())
    return bind_forecast_stock(compile_offer_projection(forecast, choices))


@pytest.fixture(scope="module")
def legacy() -> BoundOutboundStock:
    data = Path(__file__).resolve().parents[2] / "data"
    return bind_outbound_stock(
        compile_outbound_shift(
            data / "v3-proposal", data / "v3-adaptation-proposal", WorkloadPolicy(8, 0, 8, "normal")
        )
    )


@pytest.mark.parametrize("mutation", ["clock", "quantity", "receipt_owner"])
def test_legacy_wrapper_keeps_authority_before_shared_loop(mutation: str) -> None:
    timed = workload()
    original = initial()
    incoming = declared_receipts(timed)
    if mutation == "clock":
        first = timed.jobs[0]
        assert first.arrival_tick == 0
        timed = replace(timed, jobs=(replace(first, arrival_tick=False), *timed.jobs[1:]))
    elif mutation == "quantity":
        alias: Any = F(original[0].quantity_units)
        assert alias == original[0].quantity_units
        original = (replace(original[0], quantity_units=alias), *original[1:])
    else:
        incoming = (replace(incoming[0], initial_owner_id="invented-slot"), *incoming[1:])
    with pytest.raises(ValueError):
        allocate_offers(timed, original, incoming)


def test_old_and_new_public_namespaces_reject_each_other(
    stock: ForecastBoundStock, legacy: BoundOutboundStock
) -> None:
    foreign: Any = stock
    with pytest.raises(ValueError):
        verify_outbound_stock(foreign)
    with pytest.raises(ValueError):
        bind_outbound_stock(foreign.projection)
    with pytest.raises(ValueError):
        load_outbound_stock(stock.frozen_bytes)
    foreign = legacy
    with pytest.raises(ValueError):
        verify_forecast_stock(foreign)
    with pytest.raises(ValueError):
        bind_forecast_stock(foreign.inputs)
    with pytest.raises(ValueError):
        load_forecast_stock(legacy.frozen_bytes)


@pytest.mark.parametrize("location", ["placement", "status"])
def test_equal_retained_text_aliases_are_not_authority(
    stock: ForecastBoundStock, location: str
) -> None:
    if location == "placement":
        first = stock.initial_placements[0]
        changed = replace(first, slot_id=StringAlias(first.slot_id))
        forged = replace(stock, initial_placements=(changed, *stock.initial_placements[1:]))
    else:
        row = stock.allocations[0]
        alias: Any = StringAlias(row.status)
        forged = replace(stock, allocations=(replace(row, status=alias), *stock.allocations[1:]))
    assert forged == stock
    with pytest.raises(ValueError):
        verify_forecast_stock(forged)


def test_two_same_sku_offers_cannot_reuse_one_original_hu(stock: ForecastBoundStock) -> None:
    value = parse_json(stock.frozen_bytes)
    rows = [row for row in value["allocations"] if row["hu"] is not None]
    first = rows[0]
    second = next(row for row in rows[1:] if row["offer"]["sku_id"] == first["offer"]["sku_id"])
    assert first["hu"]["hu_id"] != second["hu"]["hu_id"]
    second["hu"] = first["hu"]
    with pytest.raises(ValueError):
        load_forecast_stock(canonical_bytes(value))


def test_consistent_rehashed_stock_relocation_is_still_not_source(
    stock: ForecastBoundStock,
) -> None:
    value = parse_json(stock.frozen_bytes)
    selected = next(row["hu"] for row in value["allocations"] if row["hu"] is not None)
    hu_id = selected["hu_id"]
    for hu in value["original_stock"]:
        if hu["hu_id"] == hu_id:
            hu["initial_owner_id"] = "invented-slot"
    for placement in value["initial_placements"]:
        if placement["hu_id"] == hu_id:
            placement["slot_id"] = "invented-slot"
    selected["initial_owner_id"] = "invented-slot"
    value["source_stock_hash"] = sha256_hex(value["original_stock"])
    with pytest.raises(ValueError):
        load_forecast_stock(canonical_bytes(value))


def test_stock_stage_reopens_raw_assignment_after_projection_validation(
    stock: ForecastBoundStock, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_loader = load_v3_bundle
    original_read = Path.read_bytes
    observed: list[Path] = []

    def changed(path: Path) -> bytes:
        raw = original_read(path)
        if path.name == "baseline-assignment-v3.json":
            observed.append(path)
            return raw + b" "
        return raw

    def changed_only_at_stock_stage(root: Path) -> V3Bundle:
        with monkeypatch.context() as local:
            local.setattr(Path, "read_bytes", changed)
            return original_loader(root)

    monkeypatch.setattr(forecast_stock_source, "load_v3_bundle", changed_only_at_stock_stage)
    with pytest.raises(ValueError, match="pinned bytes/SHA256 mismatch"):
        bind_forecast_stock(stock.projection)
    assert observed
