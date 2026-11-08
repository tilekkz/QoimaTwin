"""Settled state at T includes T; exposure and linear motion use [0,T)."""

from fractions import Fraction

from app.v3.pallet_cycle_state import CycleState
from app.v3.pallet_cycle_types import FIXED_ACTORS, CycleSnapshot, ExactPose


def observed_pose(state: CycleState, tick: int) -> ExactPose:
    active = state.active
    if active is None:
        return state.pose
    duration = active.planned_end_tick - active.started_tick
    fraction = Fraction(max(0, min(duration, tick - active.started_tick)), duration)
    start, end = active.operation.start_pose, active.operation.end_pose
    return ExactPose(
        start.root_z + (end.root_z - start.root_z) * fraction,
        start.fork_top + (end.fork_top - start.fork_top) * fraction,
        start.reach + (end.reach - start.reach) * fraction,
    )


def snapshot(state: CycleState, tick: int) -> CycleSnapshot:
    busy = sum(
        max(0, min(tick, end if end is not None else tick) - start) for start, end in state.busy
    )
    waiting = sum(
        max(0, min(tick, state.starts.get(job_id, tick)) - arrival)
        for job_id, arrival in state.arrivals.items()
    )
    jobs = tuple(state.jobs[key] for key in sorted(state.jobs))
    completed = sum(job.state == "complete" for job in jobs)
    return CycleSnapshot(
        tick,
        "complete" if completed == len(jobs) else "partial",
        jobs,
        state.owner,
        tuple(state.leases[key] for key in sorted(state.leases)),
        state.active,
        observed_pose(state, tick),
        tuple((actor, busy if actor == "F01" else 0) for actor in FIXED_ACTORS),
        waiting,
        completed,
    )
