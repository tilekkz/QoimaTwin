"""Finite bodies and human resources share the clock; counts follow hand arithmetic."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.light_flow_engine import LightFlowEngine
from tests.v3.test_belt_runtime import source_catalog
from tests.v3.test_light_flow_fixtures import hand_profile


def test_two_orders_share_one_cart_and_shipper_without_cloning_original_hu() -> None:
    profile = hand_profile(orders=2)
    first = LightFlowEngine(profile, source_catalog()).run(200_000_000, 240_000_000)
    second = LightFlowEngine(
        replace(profile, orders=tuple(reversed(profile.orders))), source_catalog()
    ).run(200_000_000, 240_000_000)
    assert first == second
    assert first.status == "complete" and first.at_end.tick == 228_170_000
    assert first.at_end.balance.gross_mass_kg == F("1.44")
    assert first.at_end.balance.shipped_mass_kg == F(".31")
    assert first.at_end.balance.shipped_units_by_sku == (("SKU1", 6),)
    deposits = {e.order_id: e.tick for e in first.events if e.kind == "intake_handoff"}
    assert deposits == {"O1": 13_000_000, "O2": 33_000_000}
    assert not first.at_end.leases and not first.at_end.belt.leases
    assert {c.hu_id for c in first.at_end.belt.carriers} == {"P1", "P2"}


def test_unavailable_packer_leaves_physical_station_occupied_until_real_service() -> None:
    result = LightFlowEngine(hand_profile(packer_ready=100_000_000), source_catalog()).run(
        80_000_000, 300_000_000
    )
    assert result.status == "complete" and result.at_end.tick == 253_254_552
    assert result.at_horizon.belt.carriers[0].status == "waiting"
    assert any(resource == "resource:V3_SPUR06" for resource, _ in result.at_horizon.belt.leases)
    assert not any(e.kind == "packed" and e.tick <= 80_000_000 for e in result.events)
    assert next(e.tick for e in result.events if e.kind == "packed") == 105_000_000


def test_missing_declared_package_or_invalid_geometry_is_rejected_before_start() -> None:
    profile = hand_profile()
    with pytest.raises(ValueError):
        LightFlowEngine(replace(profile, materials=profile.materials[:1]), source_catalog())
    huge = replace(
        profile.materials[1], recipe=replace(profile.materials[1].recipe, outer=(F(2), F(1), F(2)))
    )
    with pytest.raises(ValueError):
        LightFlowEngine(replace(profile, materials=(profile.materials[0], huge)), source_catalog())


def test_full_declared_shipped_owner_blocks_second_service_without_losing_package() -> None:
    profile = hand_profile(orders=2)
    owners = tuple(replace(o, capacity=1) if o.owner_id == "shipped" else o for o in profile.owners)
    result = LightFlowEngine(replace(profile, owners=owners), source_catalog()).run(
        200_000_000, 240_000_000
    )
    assert result.status == "partial"
    assert result.at_end.balance.shipped_units_by_sku == (("SKU1", 3),)
    assert result.at_end.balance.gross_mass_kg == F("1.44")
    parcel = next(c for c in result.at_end.stock.containers if c.container_id == "P2")
    assert parcel.owner_id == "actor:S01" and parcel.sealed_for == "O2"
    worker = next(w for w in result.at_end.workers if w.actor_id == "S01")
    assert worker.operation is None and worker.waiting_since == 203_170_000
    assert worker.paid_ticks == 37_000_000  # first31 + second approach2/pickup1/carry3
