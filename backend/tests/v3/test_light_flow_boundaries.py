"""Observed H/end state never completes planned future work or forbids admitted drain."""

from fractions import Fraction as F

import pytest

from app.v3.light_flow_engine import LightFlowEngine
from tests.v3.test_belt_runtime import source_catalog
from tests.v3.test_light_flow_fixtures import hand_profile


@pytest.mark.parametrize(
    "cutoff,expected_kind,planned",
    [
        (4_000_000, "pick", 6_000_000),
        (47_000_000, "pack", 48_915_448),
        (49_000_000, "clear", 49_915_448),
        (180_000_000, "shipping_service", 192_170_000),
    ],
)
def test_midoperation_cutoff_has_only_observed_events(
    cutoff: int, expected_kind: str, planned: int
) -> None:
    result = LightFlowEngine(hand_profile(), source_catalog()).run(cutoff, cutoff)
    assert result.status == "partial"
    active = [
        w.operation
        for w in result.at_end.workers
        if w.operation and w.operation.kind == expected_kind
    ]
    assert len(active) == 1 and active[0] is not None
    assert active[0].planned_end_tick == planned
    assert all(e.tick <= cutoff for e in result.events)
    assert result.at_end.balance.shipped_units_by_sku == ()
    assert result.at_end.balance.gross_mass_kg == F("1.19")
    if cutoff == 4_000_000:
        assert all(p.container_id == "HU1" for p in result.at_end.stock.locations)
    if cutoff == 49_000_000:
        assert sum(p.container_id == "P1" for p in result.at_end.stock.locations) == 3
        assert (
            next(c for c in result.at_end.stock.containers if c.container_id == "C1").owner_id
            == "belt:O1"
        )


def test_order_admitted_before_horizon_drains_all_stages_and_paid_returns() -> None:
    result = LightFlowEngine(hand_profile(), source_catalog()).run(4_000_000, 220_000_000)
    assert result.at_horizon.balance.shipped_units_by_sku == ()
    assert result.status == "complete" and result.at_end.tick == 197_170_000
    assert result.at_end.balance.shipped_units_by_sku == (("SKU1", 3),)


def test_handoff_boundary_counts_ship_but_worker_is_still_returning() -> None:
    result = LightFlowEngine(hand_profile(), source_catalog()).run(192_170_000, 195_000_000)
    assert result.at_horizon.balance.shipped_units_by_sku == (("SKU1", 3),)
    worker = next(w for w in result.at_horizon.workers if w.actor_id == "S01")
    assert worker.operation is not None and worker.operation.kind == "return"
    assert worker.paid_ticks == 26_000_000  # approach2 + pickup1 + carry3 + service20
    assert result.status == "partial" and result.at_end.tick == 195_000_000
