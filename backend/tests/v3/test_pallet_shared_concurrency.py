"""A second actual warehouse task shares the clock and ledger, not a component simulator."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.mesh_proof_fixture import LocalGeometryProof
from app.v3.pallet_shared_engine import PalletSharedEngine
from app.v3.whole_flow_models import WholeHUOrder
from tests.v3.test_pallet_cycle_clock import SOURCE
from tests.v3.test_pallet_cycle_proof import proven_fixture as proven_fixture
from tests.v3.test_pallet_shared_fixtures import PALLET, shared_profile
from tests.v3.test_receipt_flow_fixtures import receipt_conveyor


def test_small_whole_shipping_and_pallet_cycle_share_actual_workers_and_inventory(
    proven: LocalGeometryProof,
) -> None:
    profile = shared_profile(proven.mesh_sha256)
    world = replace(profile.world, orders=(WholeHUOrder("W1", 0, "HU1", "OUT_W_RETAIL"),))
    engine = PalletSharedEngine(replace(profile, world=world), receipt_conveyor(), SOURCE, proven)
    result = engine.run(6_000_000, 50_000_000)
    busy = {w.actor_id: w.order_id for w in result.at_horizon.workers}
    assert busy["F01"] == "C0" and busy["S01"] == "W1"
    assert len(result.at_horizon.inventory.claims) == 2
    assert result.at_end.pallet_jobs[0].completed_tick == 13_700_000
    assert result.at_end.whole_orders[0].shipped_tick == 37_000_000
    assert result.at_end.whole_orders[0].returned_tick == 42_000_000
    assert result.at_end.tick == 42_000_000
    assert result.at_end.balance.onsite_mass_kg == F("455.25")
    assert result.at_end.balance.shipped_mass_kg == F(".94")
    assert len(result.at_end.workers) == 24 and result.at_end.inventory.claims == ()
    assert sum(c.container_id == PALLET for c in result.at_end.stock.containers) == 1


def test_optional_two_verified_five_centimetre_bridges_add_paid_time(
    proven: LocalGeometryProof,
) -> None:
    profile = replace(shared_profile(proven.mesh_sha256), source_approach=True)
    result = PalletSharedEngine(profile, receipt_conveyor(), SOURCE, proven).run(
        20_000_000, 30_000_000
    )
    state = result.at_end.pallet_jobs[0]
    assert (state.attached_tick, state.released_tick, state.completed_tick) == (
        3_300_000,
        10_700_000,
        13_800_000,
    )
    assert result.bridge is not None and result.bridge.distance_m == F(".05")
    assert result.source_inventory_binding is False and result.pallet_receiving is False


def test_shared_arrivals_must_be_before_horizon_even_if_standalone_allows_equality(
    proven: LocalGeometryProof,
) -> None:
    profile = shared_profile(proven.mesh_sha256)
    profile = replace(profile, jobs=(replace(profile.jobs[0], ready_tick=1_000_000),))
    engine = PalletSharedEngine(profile, receipt_conveyor(), SOURCE, proven)
    with pytest.raises(ValueError, match="strictly before H"):
        engine.run(1_000_000, 30_000_000)
