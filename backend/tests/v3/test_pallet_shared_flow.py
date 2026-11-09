"""Prewritten13.7-second and conservation oracles; execution deferred by instruction."""

from fractions import Fraction as F

from app.v3.mesh_proof_fixture import LocalGeometryProof
from app.v3.pallet_cycle_types import PLATFORM_ID
from app.v3.pallet_shared_engine import PalletSharedEngine
from tests.v3.test_pallet_cycle_clock import SOURCE
from tests.v3.test_pallet_cycle_proof import proven_fixture as proven_fixture
from tests.v3.test_pallet_shared_fixtures import PALLET, VEHICLE_OWNER, shared_profile
from tests.v3.test_receipt_flow_fixtures import receipt_conveyor


def test_local_pallet_changes_real_ledger_owner_at_completed_handling(
    proven: LocalGeometryProof,
) -> None:
    result = PalletSharedEngine(
        shared_profile(proven.mesh_sha256), receipt_conveyor(), SOURCE, proven
    ).run(20_000_000, 30_000_000)
    moves = [
        (e.tick, e.delta.after[0].container.owner_id)
        for e in result.events
        if e.delta is not None and e.order_id == "C0"
    ]
    assert moves == [(3_250_000, VEHICLE_OWNER), (10_650_000, PLATFORM_ID)]
    assert result.at_end.tick == 13_700_000
    assert result.at_horizon.tick == 20_000_000
    assert len(result.at_end.workers) == 24
    assert sum(dict(result.at_end.balance.units_by_sku).values()) == 48
    assert dict(result.at_end.balance.units_by_sku)["PALLET-SKU"] == 24
    assert result.at_end.balance.onsite_mass_kg == F("456.19")
    assert result.at_end.inventory.claims == () and result.at_end.leases == ()
    assert result.shared_inventory is True and result.pallet_receiving is False


def test_cap_keeps_real_claim_and_paid_driver_after_pallet_is_released(
    proven: LocalGeometryProof,
) -> None:
    result = PalletSharedEngine(
        shared_profile(proven.mesh_sha256), receipt_conveyor(), SOURCE, proven
    ).run(11_000_000, 11_000_000)
    pallet = next(c for c in result.at_end.stock.containers if c.container_id == PALLET)
    assert pallet.owner_id == PLATFORM_ID
    driver = next(w for w in result.at_end.workers if w.actor_id == "F01")
    assert driver.order_id == "C0" and driver.operation is not None
    assert driver.paid_ticks == 11_000_000
    assert result.at_end.inventory.claims[0].container_id == PALLET
    assert dict(result.at_end.leases)["slot:" + PLATFORM_ID] == "C0"
    assert result.status == "partial"


def test_repeated_requests_share_one_hu_and_fifo_paid_driver(
    proven: LocalGeometryProof,
) -> None:
    result = PalletSharedEngine(
        shared_profile(proven.mesh_sha256, jobs=2), receipt_conveyor(), SOURCE, proven
    ).run(20_000_000, 40_000_000)
    starts = [(e.tick, e.order_id) for e in result.events if e.kind == "pallet_cycle_started"]
    assert starts == [(0, "C0"), (13_700_000, "C1")]
    assert result.at_end.tick == 27_400_000
    assert sum(c.container_id == PALLET for c in result.at_end.stock.containers) == 1
    assert dict(result.at_end.balance.units_by_sku)["PALLET-SKU"] == 24


def test_horizon_counts_attach_but_does_not_admit_waiting_second_cycle(
    proven: LocalGeometryProof,
) -> None:
    result = PalletSharedEngine(
        shared_profile(proven.mesh_sha256, jobs=2), receipt_conveyor(), SOURCE, proven
    ).run(3_250_000, 30_000_000)
    pallet = next(c for c in result.at_horizon.stock.containers if c.container_id == PALLET)
    assert pallet.owner_id == VEHICLE_OWNER
    assert result.at_end.pallet_jobs[0].completed_tick == 13_700_000
    assert result.at_end.pallet_jobs[1].admitted_tick is None
    assert result.status == "partial"


def test_active_pose_is_observed_at_cap_not_at_future_completion(
    proven: LocalGeometryProof,
) -> None:
    result = PalletSharedEngine(
        shared_profile(proven.mesh_sha256), receipt_conveyor(), SOURCE, proven
    ).run(5_000_000, 6_000_000)
    assert result.at_horizon.vehicle.pose.reach == F(".1")
    assert result.at_end.vehicle.pose.root_z == F("-.75")
    assert result.at_end.vehicle.active_operation is not None
    assert result.at_end.vehicle.active_operation.planned_end_tick == 6_300_000
    assert all(e.tick <= 6_000_000 for e in result.events)
