"""Independent human arithmetic plus the unchanged source directed-belt edge sums."""

from fractions import Fraction as F

from app.v3.light_flow_engine import LightFlowEngine
from tests.v3.test_belt_runtime import source_catalog
from tests.v3.test_light_flow_fixtures import hand_profile


def test_one_order_has_one_clock_real_stock_and_paid_worker_returns() -> None:
    result = LightFlowEngine(hand_profile(), source_catalog()).run(195_000_000, 220_000_000)
    assert result.status == "complete"
    assert result.at_end.tick == 197_170_000
    assert result.at_horizon.balance.shipped_units_by_sku == (("SKU1", 3),)
    assert result.at_end.balance.gross_mass_kg == F("1.19")  # .94 + .20 + .05
    assert result.at_end.balance.onsite_mass_kg == F("1.035")
    assert result.at_end.balance.shipped_mass_kg == F(".155")
    times = {event.kind: event.tick for event in result.events if event.order_id == "O1"}
    assert times["picked"] == 6_000_000
    assert times["intake_handoff"] == 13_000_000
    assert times["packed"] == 48_915_448
    assert times["parcel_loaded"] == 49_915_448
    assert times["output_ready"] == 166_170_000
    assert times["output_collected"] == 169_170_000
    assert times["shipped"] == 192_170_000
    assert len(result.at_end.workers) == 24
    assert not result.at_end.leases and not result.at_end.belt.leases
    shipper = next(w for w in result.at_horizon.workers if w.actor_id == "S01")
    assert shipper.operation is not None and shipper.operation.kind == "return"
    assert shipper.operation.planned_end_tick == 197_170_000
    assert all(event.tick <= result.at_end.tick for event in result.events)
