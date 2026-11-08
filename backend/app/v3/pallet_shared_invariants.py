"""Additional custody is admitted to the common checker only after physical validation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.storage.canonical_json import canonical_bytes
from app.v3.flow_profile_wire import record
from app.v3.light_flow_state import HumanStep
from app.v3.pallet_shared_authority import check_authority
from app.v3.pallet_shared_state import PalletJobState

if TYPE_CHECKING:
    from app.v3.pallet_shared_engine import PalletSharedEngine


def check_shared(engine: PalletSharedEngine) -> tuple[dict[str, str], frozenset[str]]:
    check_authority(engine)
    active = [
        s
        for s in engine.pallet_jobs.values()
        if s.admitted_tick is not None and s.completed_tick is None
    ]
    if len(active) > 1:
        raise RuntimeError("PALLET vehicle/driver has multiple active jobs")
    for job_state in engine.pallet_jobs.values():
        _progress(engine, job_state)
    _paid(engine)
    state = active[0] if active else None
    key = state.spec.job_id if state else None
    if engine.vehicle.job_id != key:
        raise RuntimeError("PALLET vehicle assignment differs from actual work")
    expected = {r: key for r in engine.pallet_resources} if key is not None else {}
    actual = {r: engine.leases[r] for r in engine.pallet_resources if r in engine.leases}
    if actual != expected:
        raise RuntimeError("PALLET physical resource reservation missing or foreign")
    p = engine.pallet_profile
    owner = p.platform_id
    claims: frozenset[str] = frozenset()
    if state is not None:
        _worker(engine, state)
        _claim(engine, state)
        claims = frozenset({"pallet:" + state.spec.job_id})
        if state.attached_tick is not None and state.released_tick is None:
            owner = p.vehicle_owner_id
    else:
        _idle(engine)
    if engine.ledger.contents(p.hu_id).container.owner_id != owner:
        raise RuntimeError("PALLET ledger custody lacks completed handling")
    return {p.hu_id: owner}, claims


def _idle(engine: PalletSharedEngine) -> None:
    worker = engine.workers["F01"]
    if (
        engine.vehicle.pose != engine.plan[0].start_pose
        or worker.order_id is not None
        or worker.operation is not None
        or worker.steps
        or worker.waiting_since is not None
        or worker.task != "idle"
        or worker.node != engine.pallet_profile.driver_anchor
    ):
        raise RuntimeError("Idle PALLET vehicle/driver has uncompleted physical work")


def _paid(engine: PalletSharedEngine) -> None:
    worker = engine.workers["F01"]
    completed = sum(
        op.duration_ticks
        for state in engine.pallet_jobs.values()
        for op in engine.plan[: state.completed_steps]
    )
    if (
        type(worker.closed_paid) is not int
        or worker.closed_paid != completed
        or type(worker.closed_queue) is not int
        or worker.closed_queue != 0
    ):
        raise RuntimeError("PALLET driver paid exposure differs from completed actual operations")


def _progress(engine: PalletSharedEngine, state: PalletJobState) -> None:
    count = state.completed_steps
    if type(count) is not int or not 0 <= count <= len(engine.plan):
        raise RuntimeError("PALLET completed operation count is invalid")
    ticks = (state.admitted_tick, state.attached_tick, state.released_tick, state.completed_tick)
    if any(t is not None and (type(t) is not int or not 0 <= t <= engine.tick) for t in ticks):
        raise RuntimeError("PALLET progress contains unobserved or noninteger completion")
    if state.admitted_tick is None:
        expected = "unreleased" if state.spec.ready_tick > engine.tick else "waiting"
        # Before the first calendar settle, an offer at zero is still unreleased.
        allowed = {expected, "unreleased"} if not engine.used else {expected}
        if count or any(t is not None for t in ticks[1:]) or state.status not in allowed:
            raise RuntimeError("PALLET progress exists without actual admission")
        return
    elapsed, attach, release = state.admitted_tick, None, None
    for op in engine.plan[:count]:
        elapsed += op.duration_ticks
        if op.kind == "attach":
            attach = elapsed
        elif op.kind == "release":
            release = elapsed
    completed = elapsed if count == len(engine.plan) else None
    if (state.attached_tick, state.released_tick, state.completed_tick) != (
        attach,
        release,
        completed,
    ):
        raise RuntimeError("PALLET completion facts differ from actual contiguous paid operations")
    if elapsed > engine.tick or (completed is None and state.status != "active"):
        raise RuntimeError("PALLET active completion state differs from clock")
    if completed is not None and state.status != "complete":
        raise RuntimeError("PALLET returned job is not marked complete")


def _worker(engine: PalletSharedEngine, state: PalletJobState) -> None:
    worker, p = engine.workers["F01"], engine.pallet_profile
    remaining = engine.plan[state.completed_steps :]
    expected = tuple(
        HumanStep(f"pallet:{op.ordinal}:{op.kind}", p.driver_anchor, op.duration_ticks)
        for op in remaining
    )
    if (
        worker.order_id != state.spec.job_id
        or worker.task != "pallet_cycle"
        or worker.node != p.driver_anchor
        or canonical_bytes(record(tuple(worker.steps))) != canonical_bytes(record(expected))
        or worker.operation is None
        or worker.waiting_since is not None
    ):
        raise RuntimeError("PALLET driver is not executing the actual shared paid plan")
    op = worker.operation
    start = state.admitted_tick
    if start is None:
        raise RuntimeError("PALLET operation lacks actual admission")
    start += sum(step.duration_ticks for step in engine.plan[: state.completed_steps])
    planned = remaining[0]
    if (
        op.kind != expected[0].kind
        or op.order_id != state.spec.job_id
        or type(op.start_tick) is not int
        or type(op.planned_end_tick) is not int
        or op.start_tick != start
        or op.planned_end_tick != start + planned.duration_ticks
        or not start <= engine.tick < op.planned_end_tick
        or op.route is not None
        or op.carrying_id is not None
        or op.cart_id is not None
        or op.source_node != p.driver_anchor
        or op.target_node != p.driver_anchor
        or engine.vehicle.pose != planned.start_pose
    ):
        raise RuntimeError("PALLET vehicle operation would teleport or finish early")


def _claim(engine: PalletSharedEngine, state: PalletJobState) -> None:
    claim = next(
        (c for c in engine.ledger.claims if c.claim_id == "pallet:" + state.spec.job_id), None
    )
    contents = engine.ledger.contents(engine.pallet_profile.hu_id)
    if (
        claim is None
        or claim.whole_hu is not True
        or claim.job_id != state.spec.job_id
        or claim.container_id != engine.pallet_profile.hu_id
        or set(claim.unit_ids) != {u.token.unit_id for u in contents.units}
    ):
        raise RuntimeError("PALLET actual job lost its exact whole-HU inventory claim")
