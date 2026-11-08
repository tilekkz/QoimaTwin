"""Prewritten settled-state corruption cases; no execution before final assembly."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.mesh_proof_fixture import LocalGeometryProof
from app.v3.pallet_cycle_types import PLATFORM_ID
from app.v3.pallet_shared_engine import PalletSharedEngine
from tests.v3.test_pallet_cycle_clock import SOURCE
from tests.v3.test_pallet_cycle_proof import proven_fixture as proven_fixture
from tests.v3.test_pallet_shared_fixtures import shared_profile
from tests.v3.test_receipt_flow_fixtures import receipt_conveyor


@pytest.mark.parametrize("resource", ["worker:F01", "vehicle:FL01", "slot:" + PLATFORM_ID])
def test_active_plan_requires_every_real_shared_resource(
    proven: LocalGeometryProof,
    resource: str,
) -> None:
    engine = PalletSharedEngine(
        shared_profile(proven.mesh_sha256), receipt_conveyor(), SOURCE, proven
    )
    engine.run(6_000_000, 6_000_000)
    del engine.leases[resource]
    with pytest.raises(RuntimeError, match="resource reservation"):
        engine._check()


def test_empty_platform_remains_reserved_until_driver_safe_return(
    proven: LocalGeometryProof,
) -> None:
    engine = PalletSharedEngine(
        shared_profile(proven.mesh_sha256), receipt_conveyor(), SOURCE, proven
    )
    result = engine.run(6_000_000, 6_000_000)
    assert not any(c.owner_id == PLATFORM_ID for c in result.at_end.stock.containers)
    assert engine._place_free(PLATFORM_ID) is False
    assert len(result.at_end.inventory.claims) == 1


def test_shared_driver_cannot_teleport_vehicle_or_finish_before_paid_interval(
    proven: LocalGeometryProof,
) -> None:
    engine = PalletSharedEngine(
        shared_profile(proven.mesh_sha256), receipt_conveyor(), SOURCE, proven
    )
    engine.run(6_000_000, 6_000_000)
    engine.vehicle.pose = replace(engine.vehicle.pose, root_z=F(100))
    with pytest.raises(RuntimeError, match=r"teleport|pose"):
        engine._check()


def test_retained_job_cannot_change_ready_tick_through_boolean_alias(
    proven: LocalGeometryProof,
) -> None:
    engine = PalletSharedEngine(
        shared_profile(proven.mesh_sha256), receipt_conveyor(), SOURCE, proven
    )
    object.__setattr__(engine.pallet_profile.jobs[0], "ready_tick", False)
    with pytest.raises(RuntimeError, match="authority"):
        engine._check()


def test_idle_vehicle_cannot_keep_a_hidden_paid_driver_operation(
    proven: LocalGeometryProof,
) -> None:
    engine = PalletSharedEngine(
        shared_profile(proven.mesh_sha256), receipt_conveyor(), SOURCE, proven
    )
    result = engine.run(20_000_000, 30_000_000)
    operation = next(e.operation for e in result.events if e.operation is not None)
    assert operation is not None
    engine.workers["F01"].operation = replace(
        operation, start_tick=13_700_000, planned_end_tick=14_700_000
    )
    with pytest.raises(RuntimeError, match="Idle PALLET"):
        engine._check()


def test_missing_active_claim_is_not_replaced_by_shadow_custody(
    proven: LocalGeometryProof,
) -> None:
    engine = PalletSharedEngine(
        shared_profile(proven.mesh_sha256), receipt_conveyor(), SOURCE, proven
    )
    engine.run(6_000_000, 6_000_000)
    engine.ledger.release_claim("pallet:C0", "C0")
    with pytest.raises(RuntimeError, match="inventory claim"):
        engine._check()


def test_completed_driver_labor_cannot_be_deleted_while_preserving_job_facts(
    proven: LocalGeometryProof,
) -> None:
    engine = PalletSharedEngine(
        shared_profile(proven.mesh_sha256), receipt_conveyor(), SOURCE, proven
    )
    engine.run(20_000_000, 30_000_000)
    engine.workers["F01"].closed_paid = 0
    with pytest.raises(RuntimeError, match="paid exposure"):
        engine._check()


def test_retained_jobs_cannot_change_immutable_collection_type(
    proven: LocalGeometryProof,
) -> None:
    engine = PalletSharedEngine(
        shared_profile(proven.mesh_sha256), receipt_conveyor(), SOURCE, proven
    )
    object.__setattr__(engine.pallet_profile, "jobs", list(engine.pallet_profile.jobs))
    with pytest.raises(RuntimeError, match="authority"):
        engine._check()
