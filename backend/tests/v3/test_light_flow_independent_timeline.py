"""Literal hand timelines fixed before inspecting the connected engine."""

from fractions import Fraction as F

from tests.v3.test_light_flow_fixtures import hand_profile
from tests.v3.test_light_flow_independent_helpers import (
    SECOND,
    assert_whole_material_mass,
    container,
    run_flow,
    transaction_ticks,
    unit_ids,
)


def test_single_three_unit_order_preserves_materials_and_paid_return_timeline() -> None:
    result = run_flow(hand_profile(), 200 * SECOND, 210 * SECOND)
    assert result.status == "complete" and result.at_end.tick == 197_170_000
    assert transaction_ticks(result, "pick") == (6_000_000,)
    assert transaction_ticks(result, "pack") == (48_915_448,)
    assert transaction_ticks(result, "ship") == (192_170_000,)
    assert result.at_end.belt.queue_ticks == 5 * SECOND  # Packer approach2 + sink hold3.
    workers = {w.actor_id: w for w in result.at_end.workers}
    assert [workers[key].paid_ticks for key in ("P01", "K06", "S01")] == [
        20 * SECOND,
        8 * SECOND,
        31 * SECOND,
    ]
    assert_whole_material_mass(result.at_end, F(119, 100))
    assert result.at_end.balance.shipped_mass_kg == F(31, 200)
    assert result.at_end.balance.onsite_mass_kg == F(207, 200)
    assert unit_ids(result.at_end, "P1") == {"U1", "U2", "U3"}
    assert len(unit_ids(result.at_end, "HU1")) == 21 and not unit_ids(result.at_end, "C1")
    assert container(result.at_end, "HU1").owner_id == "slot"
    assert container(result.at_end, "C1").owner_id == "empties"
    assert container(result.at_end, "P1").owner_id == "shipped"
    assert {c.container_id for c in result.at_end.stock.containers} == {"HU1", "C1", "P1"}


def test_two_orders_share_cart_shipper_and_original_hu_without_unit_cloning() -> None:
    profile = hand_profile(orders=2)
    result = run_flow(profile, 300 * SECOND, 400 * SECOND)
    assert result.status == "complete" and result.at_end.tick == 228_170_000
    assert transaction_ticks(result, "pick") == (6_000_000, 26_000_000)
    assert transaction_ticks(result, "pack") == (48_915_448, 68_915_448)
    assert transaction_ticks(result, "ship") == (192_170_000, 223_170_000)
    assert result.at_end.belt.queue_ticks == 21 * SECOND  # Approaches4 + sink holds3+14.
    workers = {w.actor_id: w for w in result.at_end.workers}
    assert [workers[key].paid_ticks for key in ("P01", "K06", "S01")] == [
        40 * SECOND,
        16 * SECOND,
        62 * SECOND,
    ]
    assert_whole_material_mass(result.at_end, F(36, 25))
    assert result.at_end.balance.shipped_mass_kg == F(31, 100)
    assert result.at_end.balance.onsite_mass_kg == F(113, 100)
    assert unit_ids(result.at_end, "P1") == {"U1", "U2", "U3"}
    assert unit_ids(result.at_end, "P2") == {"U4", "U5", "U6"}
    assert len(unit_ids(result.at_end, "HU1")) == 18
    assert len({u.unit_id for u in result.at_end.stock.locations}) == 24
    assert all(u.origin_hu == "HU1" for u in profile.stock.units)
    assert len(profile.stock.containers) == 1


def test_mid_pick_cutoff_does_not_commit_units_or_future_completion() -> None:
    result = run_flow(hand_profile(), 4 * SECOND, 4 * SECOND)
    snapshot = result.at_end
    assert result.status == "partial" and snapshot.tick == 4 * SECOND
    assert len(unit_ids(snapshot, "HU1")) == 24 and not unit_ids(snapshot, "C1")
    assert not transaction_ticks(result, "pick")
    worker = next(w for w in snapshot.workers if w.actor_id == "P01")
    assert worker.operation is not None
    assert worker.operation.start_tick == 3 * SECOND
    assert worker.operation.planned_end_tick == 6 * SECOND
    assert all(e.tick <= 4 * SECOND for e in result.events)
    assert_whole_material_mass(snapshot, F(119, 100))


def test_pack_and_clear_boundaries_keep_empty_carrier_until_paid_clear_finishes() -> None:
    packed = run_flow(hand_profile(), 48_915_448, 48_915_448).at_end
    assert unit_ids(packed, "P1") == {"U1", "U2", "U3"}
    assert not unit_ids(packed, "C1")
    assert container(packed, "P1").sealed_for == "O1"
    assert container(packed, "P1").owner_id == "bench"
    assert container(packed, "C1").owner_id == "belt:O1"
    assert any(c.payload_id == "C1" for c in packed.belt.carriers)
    cleared = run_flow(hand_profile(), 49_915_448, 49_915_448).at_end
    assert container(cleared, "C1").owner_id == "empties"
    assert container(cleared, "P1").owner_id == "belt:O1"
    assert any(c.payload_id == "P1" for c in cleared.belt.carriers)
    assert_whole_material_mass(packed, F(119, 100))
    assert_whole_material_mass(cleared, F(119, 100))


def test_new_second_order_cannot_be_admitted_after_horizon_when_cart_returns() -> None:
    result = run_flow(hand_profile(orders=2), 10 * SECOND, 300 * SECOND)
    orders = {o.order_id: o for o in result.at_end.orders}
    assert orders["O1"].admitted_tick == 0 and orders["O1"].shipped_tick == 192_170_000
    assert orders["O2"].admitted_tick is None and orders["O2"].shipped_tick is None
    assert result.status == "partial"
    assert transaction_ticks(result, "pick") == (6 * SECOND,)
    assert len(unit_ids(result.at_end, "HU1")) == 21
    assert dict(result.at_end.balance.shipped_units_by_sku) == {"SKU1": 3}
