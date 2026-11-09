"""Atomic N1 admission and completed handling effects on the coordinator's actual ledger."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.v3.coordinator_observe import effective_role
from app.v3.light_flow_state import HumanState
from app.v3.relocation_observe import RelocationState

if TYPE_CHECKING:
    from app.v3.relocation_engine import RelocationEngine


def resources(state: RelocationState) -> tuple[str, ...]:
    job = state.plan.job
    return (
        "relocation:worker:" + job.actor_id,
        "relocation:place:" + job.to_slot_id,
        "relocation:hu:" + job.hu_id,
    )


def wait_reason(engine: RelocationEngine, state: RelocationState) -> str | None:
    plan, job = state.plan, state.plan.job
    contents = engine.ledger.contents(job.hu_id)
    if any(c.container_id == job.hu_id for c in engine.ledger.claims):
        return "stock_claimed"
    if contents.container.owner_id != job.from_slot_id:
        return "source_moved"
    if {u.token.unit_id for u in contents.units} != set(plan.unit_ids):
        return "stock_not_intact"
    if not engine._place_free(job.to_slot_id):
        return "destination_busy"
    worker = engine.workers[job.actor_id]
    if worker.order_id is not None or not engine._worker_eligible(worker, "ship"):
        return "worker_busy"
    if worker.node != plan.actor.home:
        return "worker_not_home"
    finish = engine.tick + sum(s.duration for s in plan.steps)
    if any(
        w.actor_id == job.actor_id and w.start_tick < finish and w.end_tick > engine.tick
        for w in engine.coordinator.registry.unavailability
    ):
        return "worker_window"
    if any(
        i.actor_id == job.actor_id and i.request_tick < finish and i.restore_by_tick > engine.tick
        for i in engine.coordinator.intents
    ):
        return "role_window"
    return None


def dispatch(engine: RelocationEngine) -> None:
    if engine.tick >= engine.horizon:
        return
    for state in engine.relocations.values():
        if state.status != "waiting":
            continue
        reason = wait_reason(engine, state)
        if reason != state.wait_reason:
            state.wait_reason = reason
            engine._relocation_event("relocation_wait_changed", state)
        if reason is None:
            admit(engine, state)


def admit(engine: RelocationEngine, state: RelocationState) -> None:
    job = state.plan.job
    required = resources(state)
    worker = engine.workers[job.actor_id]
    if any(r in engine.leases for r in required) or wait_reason(engine, state) is not None:
        raise RuntimeError("RELOCATION_ATOMIC_ADMISSION_LOST")
    claim = engine.ledger.reserve_hu(
        "relocation:" + job.job_id,
        job.job_id,
        engine.ledger.revision,
        job.hu_id,
    )
    state.admitted_tick, state.status, state.wait_reason = engine.tick, "approaching", None
    state.paid_before = worker.closed_paid
    worker.order_id, worker.task = job.job_id, "relocation"
    worker.steps, worker.waiting_since = list(state.plan.steps), engine.tick
    engine.leases.update((r, job.job_id) for r in required)
    engine._relocation_event("inventory_claim_acquired", state, claim=claim)
    for resource in required:
        engine._relocation_event("relocation_resource_acquired", state, resource=resource)
    engine._relocation_event("relocation_admitted", state, worker=worker)


def completed(engine: RelocationEngine, state: RelocationState, kind: str) -> None:
    if state.plan.steps[state.completed_steps].kind != kind:
        raise RuntimeError("RELOCATION_COMPLETED_STEP_DIFFERS_FROM_PLAN")
    job = state.plan.job
    state.completed_steps += 1
    if kind == "relocation_take":
        state.taken_tick, state.status = engine.tick, "carrying"
        move(engine, state, "actor:" + job.actor_id, "relocation_taken")
    elif kind == "relocation_place":
        state.placed_tick, state.status = engine.tick, "returning"
        move(engine, state, job.to_slot_id, "relocation_placed")
        engine.derived_sources[job.hu_id] = job.to_slot_id
        for key, whole in engine.whole_orders.items():
            if whole.spec.hu_id == job.hu_id:
                engine.whole_sources[key] = job.to_slot_id
    elif kind == "relocation_approach":
        state.status = "taking"
    elif kind == "relocation_carry":
        state.status = "placing"
    engine._relocation_event("relocation_state_changed", state)


def move(engine: RelocationEngine, state: RelocationState, owner: str, kind: str) -> None:
    job = state.plan.job
    delta = engine.ledger.transfer_whole_hu(
        job.job_id + ":" + kind,
        engine.ledger.revision,
        job.hu_id,
        owner,
        claim_id="relocation:" + job.job_id,
    )
    engine._relocation_event(kind, state, delta=delta)


def finish(engine: RelocationEngine, worker: HumanState) -> None:
    if worker.steps:
        return
    state = engine.relocations[str(worker.order_id)]
    job = state.plan.job
    if state.completed_steps != 5 or worker.node != state.plan.actor.home:
        raise RuntimeError("RELOCATION_RELEASE_PRECEDES_PAID_RETURN")
    check_payment(state, worker)
    if effective_role(engine, job.actor_id) != "ship":
        raise RuntimeError("RELOCATION_RETURN_ROLE_CHANGED")
    engine.ledger.release_claim("relocation:" + job.job_id, job.job_id)
    state.returned_tick, state.status = engine.tick, "complete"
    engine._relocation_event("inventory_claim_released", state, released="relocation:" + job.job_id)
    for resource in resources(state):
        if engine.leases.get(resource) != job.job_id:
            raise RuntimeError("RELOCATION_RELEASED_ANOTHER_JOB_RESOURCE")
        del engine.leases[resource]
        engine._relocation_event("relocation_resource_released", state, resource=resource)
    worker.stop_waiting(engine.tick)
    worker.order_id, worker.task = None, "idle"
    engine._relocation_event("relocation_returned", state, worker=worker)


def check_payment(state: RelocationState, worker: HumanState) -> None:
    paid = state.paid_before + sum(s.duration for s in state.plan.steps[: state.completed_steps])
    if (
        type(state.paid_before) is not int
        or state.paid_before < 0
        or type(worker.closed_paid) is not int
        or worker.closed_paid != paid
    ):
        raise RuntimeError("RELOCATION_PAID_CLOCK_CHANGED")
