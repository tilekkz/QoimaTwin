"""Observe actual ledger custody and bounded exact vehicle interpolation at the requested cap."""

from __future__ import annotations

from fractions import Fraction
from typing import TYPE_CHECKING

from app.v3.pallet_cycle_types import ActiveOperation, ExactPose
from app.v3.pallet_shared_models import PalletSharedSnapshot, PalletVehicleView
from app.v3.whole_flow_models import WholeFlowSnapshot

if TYPE_CHECKING:
    from app.v3.pallet_shared_engine import PalletSharedEngine


def vehicle_view(engine: PalletSharedEngine, tick: int) -> PalletVehicleView:
    state, worker = engine.vehicle, engine.workers["F01"]
    active: ActiveOperation | None = None
    pose = state.pose
    if state.job_id is not None and worker.operation is not None:
        job = engine.pallet_jobs[state.job_id]
        op = engine.plan[job.completed_steps]
        active = ActiveOperation(
            state.job_id, op, worker.operation.start_tick, worker.operation.planned_end_tick
        )
        duration = active.planned_end_tick - active.started_tick
        fraction = Fraction(max(0, min(duration, tick - active.started_tick)), duration)
        start, end = op.start_pose, op.end_pose
        pose = ExactPose(
            start.root_z + (end.root_z - start.root_z) * fraction,
            start.fork_top + (end.fork_top - start.fork_top) * fraction,
            start.reach + (end.reach - start.reach) * fraction,
        )
    p = engine.pallet_profile
    owner = engine.ledger.contents(p.hu_id).container.owner_id
    return PalletVehicleView(
        "FL01",
        "F01",
        p.driver_anchor,
        "pallet_fixture_local",
        pose,
        active,
        state.job_id,
        p.hu_id if owner == p.vehicle_owner_id else None,
    )


def snapshot(engine: PalletSharedEngine, base: WholeFlowSnapshot) -> PalletSharedSnapshot:
    return PalletSharedSnapshot(
        base.tick,
        base.stock,
        base.balance,
        base.workers,
        base.orders,
        base.leases,
        base.belt,
        base.last_seq,
        base.cart,
        base.inventory,
        base.receipts,
        base.whole_orders,
        tuple(s.view() for _, s in sorted(engine.pallet_jobs.items())),
        vehicle_view(engine, base.tick),
    )
