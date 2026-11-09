"""Hand boundary oracles: paid safe return, exact-H admission and one repeated HU."""

import json
from fractions import Fraction as F

import pytest

from app.v3.mesh_proof_fixture import LocalGeometryProof
from app.v3.mesh_proof_source import ACTION_PATH
from app.v3.pallet_cycle_types import CycleOutcome
from tests.v3.test_pallet_independent_helpers import (
    ARC,
    HU_ID,
    PROOF_ROOT,
    new_engine,
    request,
)
from tests.v3.test_pallet_independent_helpers import (
    independent_proof_fixture as independent_proof_fixture,
)


@pytest.fixture(name="two_cycles", scope="module")
def two_cycles_fixture(independent_proof: LocalGeometryProof) -> CycleOutcome:
    return new_engine(independent_proof, (request("B"), request("A")), bridge=True).run(
        13_800_000, 30_000_000
    )


def test_positive_horizon_arrival_starts_but_cap_never_completes_planned_bridge(
    independent_proof: LocalGeometryProof,
) -> None:
    result = new_engine(independent_proof, (request("A", 7_000_000),), bridge=True).run(
        7_000_000, 7_025_000
    )
    assert result.at_horizon.active_operation is not None
    assert result.at_horizon.active_operation.started_tick == 7_000_000
    assert dict(result.at_horizon.actor_busy_ticks)["F01"] == 0
    end = result.at_end
    assert end.tick == 7_025_000 and end.status == "partial"
    assert end.active_operation is not None and end.active_operation.planned_end_tick == 7_050_000
    assert end.observed_pose.root_z == F(-41, 40)  # Half of the exact 0.05m entry.
    assert end.owner.kind == "platform" and len(end.leases) == 12
    assert dict(end.actor_busy_ticks)["F01"] == 25_000
    assert not any(e.kind in {"operation_completed", "cycle_completed"} for e in result.events)
    assert all(e.tick <= 7_025_000 for e in result.events)


def test_release_to_platform_does_not_end_paid_safe_return(
    independent_proof: LocalGeometryProof,
) -> None:
    result = new_engine(independent_proof, (request("A"),)).run(10_650_000, 11_000_000)
    assert result.at_horizon.owner.kind == result.at_end.owner.kind == "platform"
    assert len(result.at_horizon.leases) == len(result.at_end.leases) == 5
    assert result.at_end.observed_pose.root_z == F(-7, 20)  # 0.35s * 1m/s withdrawal.
    active = result.at_end.active_operation
    assert active is not None and active.operation.phase == "controlled_withdraw"
    assert active.started_tick == 10_650_000 and active.planned_end_tick == 11_700_000
    assert dict(result.at_end.actor_busy_ticks)["F01"] == 11_000_000
    assert not any(e.kind in {"lease_released", "cycle_completed"} for e in result.events)


def test_exact_h_completion_then_second_admission_preserves_one_physical_hu(
    two_cycles: CycleOutcome,
) -> None:
    result = two_cycles
    assert [(e.tick, e.job_id) for e in result.events if e.kind == "cycle_started"] == [
        (0, "A"),
        (13_800_000, "B"),
    ]
    assert result.at_horizon.completed_count == 1 and result.at_end.completed_count == 2
    assert result.at_horizon.active_operation is not None
    assert result.at_horizon.active_operation.job_id == "B"
    assert result.at_end.tick == 27_600_000 and result.at_end.leases == ()
    assert dict(result.at_horizon.actor_busy_ticks)["F01"] == 13_800_000
    assert dict(result.at_end.actor_busy_ticks)["F01"] == 27_600_000
    assert all(t == 0 for actor, t in result.at_end.actor_busy_ticks if actor != "F01")
    assert result.at_end.queue_exposure_tick_jobs == 13_800_000
    assert len(result.physical_registry) == 1
    pallet = result.physical_registry[0]
    assert (pallet.hu_id, pallet.units, pallet.gross_mass_kg) == (HU_ID, 24, F(455))
    assert {e.owner.hu_id for e in result.events if e.owner is not None} == {HU_ID}
    assert result.inventory_integration is result.operational_admission is False


def test_all_resources_hold_through_both_safe_returns(two_cycles: CycleOutcome) -> None:
    result = two_cycles
    core = {
        "worker:F01",
        "vehicle:FL01",
        "slot:v3:slot:HEAVY_E:001:L1:B1",
        f"hu:{HU_ID}",
        "action_space:v3:slot:HEAVY_E:001:L1:B1:pallet_cycle",
    }
    assert result.bridge is not None
    expected = core | set(result.bridge.resource_ids)
    assert len(expected) == 12
    for job_id, start, finish in (("A", 0, 13_800_000), ("B", 13_800_000, 27_600_000)):
        events = [e for e in result.events if e.job_id == job_id]
        acquired = [e for e in events if e.kind == "lease_acquired"]
        released = [e for e in events if e.kind == "lease_released"]
        assert {e.lease.resource_id for e in acquired if e.lease} == expected
        assert {e.lease.resource_id for e in released if e.lease} == expected
        assert all(e.tick == start for e in acquired) and all(e.tick == finish for e in released)
    boundary = [e for e in result.events if e.tick == 13_800_000]
    assert max(e.seq for e in boundary if e.kind == "lease_released") < min(
        e.seq for e in boundary if e.kind == "lease_acquired"
    )


def test_original_thirteen_source_intervals_are_preserved_beside_two_bridges(
    two_cycles: CycleOutcome,
    independent_proof: LocalGeometryProof,
) -> None:
    result = two_cycles
    keys = json.loads((PROOF_ROOT / ACTION_PATH).read_text(encoding="utf-8"))["keys"]
    assert len(keys) - 1 == len(result.geometry_proof.segments) == 13
    assert result.geometry_proof is independent_proof
    assert result.proof_bindings == independent_proof.bindings
    assert result.bridge is not None
    assert result.bridge.entry_cover_checks > 0 and result.bridge.exit_cover_checks > 0
    for job_id in ("A", "B"):
        operations = [
            e.operation.operation
            for e in result.events
            if e.job_id == job_id and e.kind == "operation_completed" and e.operation
        ]
        original = [o for o in operations if o.kind in {"motion", "hold"}]
        assert [o.phase for o in original] == [k["phase"] for k in keys[:-1]]
        assert [o.attached for o in original] == [k["attached"] for k in keys[:-1]]
        for operation, first, second in zip(original, keys, keys[1:], strict=False):
            for field in ("root_z", "fork_top", "reach"):
                assert getattr(operation.start_pose, field) == F(str(first[field]))
                assert getattr(operation.end_pose, field) == F(str(second[field]))
        bridges = [o for o in operations if o.kind == "bridge"]
        assert [o.source_arc_id for o in bridges] == [ARC + "r", ARC + "f"]
        assert [o.duration_ticks for o in bridges] == [50_000, 50_000]
