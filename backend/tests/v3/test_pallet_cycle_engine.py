"""Analytical 13.7-second local cycle, paid return and one physical HU."""

from fractions import Fraction as F

from app.v3.mesh_proof_fixture import LocalGeometryProof
from app.v3.pallet_cycle_engine import PalletCycleEngine
from app.v3.pallet_cycle_types import CycleJob, PhysicalPallet
from tests.v3.test_pallet_cycle_clock import SOURCE, timing
from tests.v3.test_pallet_cycle_proof import proven_fixture as proven_fixture


def engine(proof: LocalGeometryProof, jobs: tuple[CycleJob, ...]) -> PalletCycleEngine:
    hu = PhysicalPallet("physical-PALLET-1", "PALLET_LOAD", 24, F(455), proof.mesh_sha256)
    return PalletCycleEngine(timing(), jobs, hu, SOURCE, proof)


def job(name: str, ready: int = 0) -> CycleJob:
    return CycleJob(name, ready, "physical-PALLET-1")


def test_complete_cycle_has_distinct_handover_and_paid_safe_return(
    proven: LocalGeometryProof,
) -> None:
    result = engine(proven, (job("A"),)).run(20_000_000, 30_000_000)
    handovers = [(e.tick, e.owner.kind) for e in result.events if e.owner is not None]
    assert handovers == [(3_250_000, "vehicle"), (10_650_000, "platform")]
    assert result.at_end.tick == 13_700_000
    assert result.at_horizon.tick == 20_000_000
    assert result.at_end.status == result.at_horizon.status == "complete"
    assert dict(result.at_horizon.actor_busy_ticks)["F01"] == 13_700_000
    assert len(result.at_horizon.actor_busy_ticks) == 24
    assert result.at_end.owner.hu_id == "physical-PALLET-1"
    assert result.at_end.owner.kind == "platform"
    assert result.at_end.leases == ()
    assert result.inventory_integration is result.operational_admission is False


def test_shared_actor_platform_and_hu_are_fifo_leased_without_cloning(
    proven: LocalGeometryProof,
) -> None:
    result = engine(proven, (job("B"), job("A"))).run(20_000_000, 40_000_000)
    starts = [(e.tick, e.job_id) for e in result.events if e.kind == "cycle_started"]
    assert starts == [(0, "A"), (13_700_000, "B")]
    assert result.at_horizon.completed_count == 1
    assert result.at_end.completed_count == 2
    assert result.at_end.tick == 27_400_000
    assert result.at_horizon.owner.kind == "vehicle"
    assert dict(result.at_horizon.actor_busy_ticks)["F01"] == 20_000_000
    assert result.at_end.queue_exposure_tick_jobs == 13_700_000
    assert {e.owner.hu_id for e in result.events if e.owner} == {"physical-PALLET-1"}


def test_horizon_includes_attach_but_does_not_admit_waiting_work_after_h(
    proven: LocalGeometryProof,
) -> None:
    result = engine(proven, (job("A"), job("B"))).run(3_250_000, 40_000_000)
    assert result.at_horizon.owner.kind == "vehicle"
    assert result.at_end.completed_count == 1
    assert result.at_end.status == "partial"
    assert result.at_end.tick == 13_700_000
    assert result.at_end.jobs[1].state == "waiting"
    assert result.at_end.jobs[1].wait_reason == "horizon_closed"


def test_cap_keeps_observed_pose_separate_from_planned_future_end(
    proven: LocalGeometryProof,
) -> None:
    result = engine(proven, (job("A"),)).run(5_000_000, 6_000_000)
    assert result.at_horizon.observed_pose.reach == F(1, 10)
    assert result.at_end.tick == 6_000_000
    assert result.at_end.observed_pose.root_z == F(-3, 4)
    assert result.at_end.owner.kind == "vehicle"
    assert len(result.at_end.leases) == 5
    assert result.at_end.active_operation is not None
    assert result.at_end.active_operation.planned_end_tick == 6_300_000
    assert all(e.tick <= 6_000_000 for e in result.events)


def test_equal_tick_start_has_zero_horizon_exposure(proven: LocalGeometryProof) -> None:
    result = engine(proven, (job("A"),)).run(0, 20_000_000)
    assert dict(result.at_horizon.actor_busy_ticks)["F01"] == 0
    assert result.at_horizon.active_operation is not None
    assert result.at_horizon.active_operation.started_tick == 0


def test_input_order_does_not_change_deterministic_events(proven: LocalGeometryProof) -> None:
    first = engine(proven, (job("A"), job("B"))).run(20_000_000, 40_000_000)
    second = engine(proven, (job("B"), job("A"))).run(20_000_000, 40_000_000)
    assert first == second
