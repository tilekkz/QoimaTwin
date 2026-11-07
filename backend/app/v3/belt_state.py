"""Mutable execution bookkeeping and immutable settled observations."""

from dataclasses import dataclass
from fractions import Fraction as F

from app.v3.belt_geometry import footprint, requirements
from app.v3.belt_models import BeltCarrier, BeltJob, BeltMotion, BeltPose, BeltSnapshot, BeltStep
from app.v3.conveyor_models import ConveyorSource


@dataclass
class RunningCarrier:
    job: BeltJob
    steps: tuple[BeltStep, ...]
    index: int = 0
    arrived: bool = False
    admitted: bool = False
    complete: bool = False
    pose: BeltPose | None = None
    active: BeltMotion | None = None
    waiting_since: int | None = None
    closed_queue_ticks: int = 0

    def stop_waiting(self, tick: int) -> None:
        if self.waiting_since is not None:
            self.closed_queue_ticks += tick - self.waiting_since
            self.waiting_since = None

    def queue_ticks(self, tick: int) -> int:
        return self.closed_queue_ticks + (
            tick - self.waiting_since if self.waiting_since is not None else 0
        )


def observed_pose(state: RunningCarrier, tick: int) -> BeltPose | None:
    if state.active is None:
        return state.pose
    motion = state.active
    progress = F(tick - motion.start_tick, motion.planned_end_tick - motion.start_tick)
    if not 0 <= progress <= 1:
        raise RuntimeError("Observation lies outside active motion interval")
    start, end = motion.start, motion.end
    return BeltPose(
        start.edge_id,
        start.progress + (end.progress - start.progress) * progress,
        start.yaw_quarters + (end.yaw_quarters - start.yaw_quarters) * progress,
    )


def carrier_view(source: ConveyorSource, state: RunningCarrier, tick: int) -> BeltCarrier:
    pose = observed_pose(state, tick)
    status = "unreleased"
    if state.arrived:
        status = "waiting" if state.admitted else "outside"
    if state.active is not None:
        status = state.active.phase
    if state.complete:
        status = "complete"
    occupied = (
        footprint(source, state.job.payload, pose)
        if pose is not None and not state.complete
        else frozenset()
    )
    return BeltCarrier(
        state.job.job_id,
        state.job.hu_id,
        state.job.payload.payload_id,
        status,
        pose,
        state.active,
        tuple(sorted(occupied)),
    )


def snapshot(
    source: ConveyorSource, states: tuple[RunningCarrier, ...], leases: dict[str, str], tick: int
) -> BeltSnapshot:
    return BeltSnapshot(
        tick,
        sum(s.arrived for s in states),
        sum(s.complete for s in states),
        tuple(carrier_view(source, state, tick) for state in states),
        tuple(sorted(leases.items())),
        sum(s.queue_ticks(tick) for s in states),
    )


def settled_invariants(
    source: ConveyorSource, states: tuple[RunningCarrier, ...], leases: dict[str, str], tick: int
) -> None:
    validate_lease_universe(source, states, leases)
    owners: dict[str, str] = {}
    for state in states:
        view = carrier_view(source, state, tick)
        if state.queue_ticks(tick) < 0:
            raise RuntimeError("Negative queue exposure")
        for cell in view.occupied_cells:
            if cell in owners:
                raise RuntimeError("Conveyor cell collision")
            owners[cell] = state.job.job_id
        needed = requirements(source, frozenset(view.occupied_cells)) | planned_reservations(state)
        if any(leases.get(resource) != state.job.job_id for resource in needed):
            raise RuntimeError("Physical footprint or current plan lacks required reservation")
        if state.complete and any(owner == state.job.job_id for owner in leases.values()):
            raise RuntimeError("Completed carrier leaked resource")
        if state.active is not None and state.active.planned_end_tick <= tick:
            raise RuntimeError("Unsettled motion completion")


def planned_reservations(state: RunningCarrier) -> frozenset[str]:
    """Active swept cells and already-acquired guards remain owned before body entry."""
    if not state.admitted or state.complete:
        return frozenset()
    if not 0 <= state.index < len(state.steps):
        raise RuntimeError("Admitted carrier has no current compiled step")
    step = state.steps[state.index]
    motion = state.active
    if motion is not None:
        if (motion.phase, motion.start, motion.end) != (step.phase, step.start, step.end):
            raise RuntimeError("Active motion differs from current compiled step")
        if motion.planned_end_tick - motion.start_tick != step.duration_tick:
            raise RuntimeError("Active motion duration differs from compiled step")
        return step.resources | step.guards
    # A blocked next step may introduce a guard not acquired yet. Only guards
    # spanning the completed and next steps must already be held while waiting.
    return step.guards & state.steps[state.index - 1].guards if state.index else frozenset()


def validate_lease_universe(
    source: ConveyorSource, states: tuple[RunningCarrier, ...], leases: dict[str, str]
) -> None:
    known = {state.job.job_id: state for state in states}
    if len(known) != len(states) or len({s.job.hu_id for s in states}) != len(states):
        raise RuntimeError("Duplicate physical ownership identity")
    if len({s.job.payload.payload_id for s in states}) != len(states):
        raise RuntimeError("Duplicate carrier identity")
    allowed = {"cell:" + identity for identity in source.cells}
    allowed.update("resource:" + r.resource_id for r in source.resources.values() if r.exclusive)
    for resource, owner in leases.items():
        if resource not in allowed or owner not in known:
            raise RuntimeError("Unknown resource or owner")
        if not known[owner].admitted or known[owner].complete:
            raise RuntimeError("Inactive carrier owns resource")
    for state in states:
        if state.complete and (not state.arrived or not state.admitted):
            raise RuntimeError("Unreleased HU cannot complete without physical admission")
        if state.admitted and (not state.arrived or state.pose is None):
            raise RuntimeError("Admitted carrier lacks arrival or physical pose")
        if state.active is not None and (not state.admitted or state.complete):
            raise RuntimeError("Invalid moving-carrier lifecycle")
        if (state.active is not None or state.complete) and state.waiting_since is not None:
            raise RuntimeError("Moving or completed carrier is incorrectly queued")
        if (
            state.arrived
            and not state.complete
            and state.active is None
            and state.waiting_since is None
        ):
            raise RuntimeError("Waiting carrier lacks queue start")
