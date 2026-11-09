"""Settled checkpoints are current mutable state, never a reconstruction from the final ledger."""

from app.v3.light_flow_engine import LightFlowEngine
from tests.v3.test_belt_runtime import source_catalog
from tests.v3.test_light_flow_fixtures import hand_profile


def test_thirty_second_checkpoints_have_observed_ownership_and_event_watermarks() -> None:
    result = LightFlowEngine(hand_profile(), source_catalog()).run(195_000_000, 220_000_000)
    assert tuple(s.tick for s in result.checkpoints) == (
        0,
        30_000_000,
        60_000_000,
        90_000_000,
        120_000_000,
        150_000_000,
        180_000_000,
        197_170_000,
    )
    for snapshot in result.checkpoints:
        assert snapshot.last_seq == max(
            (e.seq for e in result.events if e.tick <= snapshot.tick), default=-1
        )
    initial, moving = result.checkpoints[:2]
    assert all(location.container_id == "HU1" for location in initial.stock.locations)
    assert sum(location.container_id == "C1" for location in moving.stock.locations) == 3
    assert result.checkpoints[-1].balance.shipped_units_by_sku == (("SKU1", 3),)
