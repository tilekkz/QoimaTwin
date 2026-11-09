"""Caller serialization follows patch-dependent offers without running another forecast."""

import json
import platform
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

from app.storage.canonical_json import canonical_bytes, sha256_hex
from app.v3 import offer_forecast_kernel
from app.v3.forecast_stock_models import ForecastBoundStock
from app.v3.offer_projection_materialize import materialize_projection
from app.v3.outbound_placement_source import source_bundle
from app.v3.outbound_stock_allocation import _allocate_verified_offers
from tests.v3.test_forecast_placement_fixtures import stock
from tests.v3.test_offer_planning_cli_fixtures import arguments

__all__ = ["stock"]


@pytest.mark.parametrize("patch_version", ["3.12.10", "3.12.15"])
def test_caller_binds_the_projected_offer_for_each_python_patch(
    stock: ForecastBoundStock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    patch_version: str,
) -> None:
    monkeypatch.setattr(platform, "python_version", lambda: patch_version)
    forecast = json.loads(stock.projection.forecast_bytes)
    forecast["kernel_identity"] = offer_forecast_kernel.identity()
    predictions = tuple((sku, Fraction(*value)) for sku, value in forecast["predictions"])
    ports = {
        port.port_id: frozenset(port.allowed_cargo_archetype_ids)
        for port in source_bundle().ports
        if port.direction == "outbound"
    }
    offers = materialize_projection(
        stock.projection.source, predictions, stock.projection.choices, ports, sha256_hex(forecast)
    )
    projection = replace(stock.projection, forecast_bytes=canonical_bytes(forecast), offers=offers)
    rows = _allocate_verified_offers(offers.jobs, stock.original_stock, ())
    runtime_stock = replace(stock, projection=projection, allocations=rows)
    bound = [row for row in rows if row.status == "original_bound"]
    assert len(bound) == 1 and sum(row.status == "unallocated" for row in rows) == 3
    arguments(tmp_path / "caller", tmp_path / "out", runtime_stock)
    choices = json.loads((tmp_path / "caller/placement_choices.json").read_bytes())
    customer = choices["candidates"][0]["customer"]
    assert (customer["offer_id"], customer["port_id"]) == (
        bound[0].offer.job_id,
        bound[0].offer.port_id,
    )
