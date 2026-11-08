"""Pre-engine arithmetic for one actual receipt, unit order and local PALLET cycle."""

from dataclasses import replace
from fractions import Fraction as F

from app.v3.mesh_proof_fixture import LocalGeometryProof
from app.v3.pallet_shared_engine import PalletSharedEngine
from tests.v3.test_light_flow_fixtures import hand_orders
from tests.v3.test_pallet_cycle_clock import SOURCE
from tests.v3.test_pallet_cycle_proof import proven_fixture as proven_fixture
from tests.v3.test_pallet_shared_fixtures import shared_profile
from tests.v3.test_receipt_flow_fixtures import receipt_conveyor, receipt_hand_profile


def test_receipt_credit_and_unit_order_use_the_same_ledger_as_local_pallet(
    proven: LocalGeometryProof,
) -> None:
    profile = shared_profile(proven.mesh_sha256)
    original = receipt_hand_profile()
    flow = replace(profile.world.receipts.flow, orders=hand_orders(1))
    receipts = replace(original, flow=flow)
    profile = replace(profile, world=replace(profile.world, receipts=receipts))
    engine = PalletSharedEngine(profile, receipt_conveyor(), SOURCE, proven)
    result = engine.run(12_000_000, 210_000_000)
    assert sum(dict(result.at_horizon.balance.units_by_sku).values()) == 72
    assert result.at_horizon.receipts[0].credited_tick == 12_000_000
    assert result.at_end.receipts[0].placed_tick == 23_000_000
    assert result.at_end.receipts[0].returned_tick == 33_000_000
    assert result.at_end.pallet_jobs[0].completed_tick == 13_700_000
    assert result.at_end.orders[0].shipped_tick == 192_170_000
    assert result.at_end.tick == 197_170_000
    assert result.at_end.balance.gross_mass_kg == F("457.13")
    assert result.at_end.balance.onsite_mass_kg == F("456.975")
    assert result.at_end.balance.shipped_mass_kg == F(".155")
    assert dict(result.at_end.balance.shipped_units_by_sku) == {"SKU1": 3}
    assert len(result.at_end.workers) == 24
    assert result.at_end.inventory.claims == () and result.at_end.leases == ()
