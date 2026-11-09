"""Declared DEMO113-only synthetic signal and explicit source-compatible customer choices."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.storage.canonical_json import canonical_bytes
from app.v3.forecast_stock_binding import bind_forecast_stock
from app.v3.forecast_stock_models import ForecastBoundStock
from app.v3.offer_forecast import fit_offer_forecast
from app.v3.offer_history import compile_offer_history
from app.v3.offer_projection_inputs import compile_offer_projection
from app.v3.offer_projection_models import OfferProjectionChoices
from app.v3.outbound_placement_models import PlacementCandidate, PlacementCustomer
from app.v3.workload_models import WorkloadPolicy
from tests.v3.test_offer_history_fixtures import choices as history_choices
from tests.v3.test_offer_history_fixtures import history_bytes
from tests.v3.test_outbound_placement_inputs import HU, candidate, choices

__all__ = ["HU", "candidate", "choices"]


def explicit_history() -> bytes:
    original = history_bytes(0, 0).decode().splitlines()
    rows = [original[0]]
    for row in original[1:]:
        day, sku, _ = row.split(",")
        rows.append(f"{day},{sku},{int(sku == 'DEMO_113')}")
    return ("\n".join(rows) + "\n").encode()


@pytest.fixture(scope="session")
def stock() -> ForecastBoundStock:
    history = compile_offer_history(explicit_history(), history_choices())
    forecast = fit_offer_forecast(history, "mean28")
    policy = WorkloadPolicy(1_000_000_000, 0, 4, "normal")
    source_mix = compile_offer_projection(
        forecast, OfferProjectionChoices(policy, "source_c10", ())
    )
    mix = tuple(
        replace(row, weight=F(int(row.port_id == "OUT_S_EXPRESS")))
        if row.sku_id == "DEMO_113"
        else row
        for row in source_mix.offers.port_mix
    )
    projection = compile_offer_projection(forecast, OfferProjectionChoices(policy, "explicit", mix))
    return bind_forecast_stock(projection)


def source_candidate(stock: ForecastBoundStock) -> PlacementCandidate:
    rows = [row for row in stock.allocations if row.hu is not None and row.hu.hu_id == HU]
    assert len(rows) == 1 and rows[0].offer.port_id == "OUT_S_EXPRESS"
    buffer = canonical_bytes(
        {
            "place_id": "v3:buffer:OUT_S_EXPRESS:08",
            "port_id": "OUT_S_EXPRESS",
            "zone_id": "STAGE_OUT_S_EXPRESS",
            "bounds_xz": ["38.4", "4.4", "39.6", "5.6"],
            "path_xz": [["48", "6"], ["39", "6"], ["39", "5"]],
            "height_m": "1.2",
            "max_payload_kg": "15",
        }
    )
    customer = PlacementCustomer(
        rows[0].offer.job_id, "OUT_S_EXPRESS", buffer, 1_000_000, 1_000_000, 30_000_000
    )
    return candidate(customer)
