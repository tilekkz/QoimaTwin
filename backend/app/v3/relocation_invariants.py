"""Retained authority, exact completed custody, and unchanged existing world validators."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.v3.coordinator_invariants import check_roles
from app.v3.coordinator_observe import effective_role
from app.v3.coordinator_packing_invariants import check_packing
from app.v3.coordinator_units_invariants import check_units
from app.v3.coordinator_units_shipping import check_shipping
from app.v3.flow_profile_sources import _same_types
from app.v3.light_flow_engine import LightFlowEngine
from app.v3.light_flow_models import FlowOperation
from app.v3.receipt_flow_invariants import check_receipt_world
from app.v3.relocation_models import RelocationProfile
from app.v3.relocation_observe import RelocationState
from app.v3.relocation_runtime import check_payment, resources
from app.v3.whole_flow_invariants import check_whole_world

if TYPE_CHECKING:
    from app.v3.relocation_engine import RelocationEngine


def authority(profile: RelocationProfile) -> str:
    # DirectedGraph intentionally omits adjacency from repr; bind every arc separately.
    return repr(profile) + repr(profile.coordinator.world.receipts.flow.graph.arcs)


def exact(actual: object, expected: object) -> bool:
    return _same_types(actual, expected) and actual == expected


def check_authority(engine: RelocationEngine) -> None:
    if authority(engine.relocation_profile) != engine.relocation_authority:
        raise RuntimeError("RELOCATION_PROFILE_AUTHORITY_CHANGED")
    if engine.coordinator is not engine.relocation_profile.coordinator:
        raise RuntimeError("RELOCATION_COORDINATOR_AUTHORITY_CHANGED")
    if engine.profile is not engine.coordinator.world.receipts.flow:
        raise RuntimeError("RELOCATION_FLOW_AUTHORITY_CHANGED")
    if not exact(engine.capabilities, {w.actor_id: w for w in engine.coordinator.registry.workers}):
        raise RuntimeError("RELOCATION_CAPABILITY_AUTHORITY_CHANGED")
    places = {p.owner_id: p for p in engine.coordinator.world.places}
    places.update((s.plan.target.owner_id, s.plan.target) for s in engine.relocations.values())
    if not exact(engine.whole_places, places):
        raise RuntimeError("RELOCATION_PLACE_AUTHORITY_CHANGED")
    if tuple(engine.relocations) != tuple(j.job_id for j in engine.relocation_profile.jobs):
        raise RuntimeError("RELOCATION_JOB_IDENTITY_CHANGED")
    if repr(tuple(s.plan for s in engine.relocations.values())) != engine.plan_authority:
        raise RuntimeError("RELOCATION_PLAN_AUTHORITY_CHANGED")
    expected = {
        s.plan.job.hu_id: s.plan.job.to_slot_id
        for s in engine.relocations.values()
        if s.placed_tick is not None
    }
    if engine.derived_sources != expected:
        raise RuntimeError("RELOCATION_DERIVED_LOCATION_CHANGED")
    original = {c.container_id: c.owner_id for c in engine.profile.stock.containers}
    original.update((o.definition.hu_id, o.slot_owner_id) for o in engine.receipt_profile.receipts)
    for key, state in engine.whole_orders.items():
        wanted = expected.get(state.spec.hu_id, original[state.spec.hu_id])
        if engine.whole_sources[key] != wanted:
            raise RuntimeError("RELOCATION_DERIVED_WHOLE_SOURCE_CHANGED")
    for relocation in engine.relocations.values():
        if not exact(engine.workers[relocation.plan.job.actor_id].spec, relocation.plan.actor):
            raise RuntimeError("RELOCATION_ACTOR_AUTHORITY_CHANGED")


def check_runtime(engine: RelocationEngine, *, due: bool = False) -> None:
    check_authority(engine)
    expected: dict[str, str] = {}
    for state in engine.relocations.values():
        _timing(engine, state)
        if state.admitted_tick is None:
            continue
        if state.returned_tick is None:
            _active(engine, state, due=due)
            expected.update((r, state.plan.job.job_id) for r in resources(state))
        _custody(engine, state)
    actual = {k: v for k, v in engine.leases.items() if k.startswith("relocation:")}
    if actual != expected:
        raise RuntimeError("RELOCATION_RESOURCE_OWNERSHIP_CHANGED")


def _timing(engine: RelocationEngine, state: RelocationState) -> None:
    count, admitted = state.completed_steps, state.admitted_tick
    if type(count) is not int or not 0 <= count <= 5:
        raise RuntimeError("RELOCATION_INVALID_COMPLETED_STEPS")
    if admitted is None:
        if count or any(
            t is not None for t in (state.taken_tick, state.placed_tick, state.returned_tick)
        ):
            raise RuntimeError("RELOCATION_HANDLING_PRECEDES_ADMISSION")
        if state.status not in {"waiting", "unreleased"}:
            raise RuntimeError("RELOCATION_UNADMITTED_STATUS_CHANGED")
        return
    if type(admitted) is not int or not state.plan.job.arrival_tick <= admitted < engine.horizon:
        raise RuntimeError("RELOCATION_INVALID_ADMISSION_TICK")
    for step_count, actual in (
        (2, state.taken_tick),
        (4, state.placed_tick),
        (5, state.returned_tick),
    ):
        expected = admitted + sum(s.duration for s in state.plan.steps[:step_count])
        if (actual is None) != (count < step_count) or (
            actual is not None
            and (type(actual) is not int or actual != expected or actual > engine.tick)
        ):
            raise RuntimeError("RELOCATION_COMPLETED_TICK_CHANGED")
    statuses = ("approaching", "taking", "carrying", "placing", "returning", "complete")
    if state.status != statuses[count]:
        raise RuntimeError("RELOCATION_PHASE_CHANGED")


def _active(engine: RelocationEngine, state: RelocationState, *, due: bool) -> None:
    plan, job = state.plan, state.plan.job
    worker = engine.workers[job.actor_id]
    check_payment(state, worker)
    if worker.order_id != job.job_id or worker.task != "relocation":
        raise RuntimeError("RELOCATION_ACTOR_RELEASED_BEFORE_RETURN")
    if effective_role(engine, job.actor_id) != "ship":
        raise RuntimeError("RELOCATION_ACTIVE_ROLE_CHANGED")
    if not exact(worker.steps, list(plan.steps[state.completed_steps :])):
        raise RuntimeError("RELOCATION_REMAINING_STEPS_CHANGED")
    operation, step = worker.operation, plan.steps[state.completed_steps]
    start = int(state.admitted_tick or 0) + sum(
        s.duration for s in plan.steps[: state.completed_steps]
    )
    previous = (
        plan.actor.home
        if state.completed_steps == 0
        else plan.steps[state.completed_steps - 1].target
    )
    expected = FlowOperation(
        step.kind,
        job.job_id,
        start,
        start + step.duration,
        previous,
        step.target,
        step.route,
        step.carrying_id,
        step.cart_id,
    )
    if operation is None or not exact(operation, expected):
        raise RuntimeError("RELOCATION_OPERATION_CHANGED")
    if any(type(t) is not int for t in (operation.start_tick, operation.planned_end_tick)):
        raise RuntimeError("RELOCATION_OPERATION_TICK_TYPE_CHANGED")
    if operation.planned_end_tick < engine.tick or (
        not due and operation.planned_end_tick == engine.tick
    ):
        raise RuntimeError("RELOCATION_OPERATION_NOT_SETTLED")
    if worker.node != (None if step.route is not None else step.target):
        raise RuntimeError("RELOCATION_ACTOR_LOCATION_CHANGED")
    _claim(engine, state)


def _claim(engine: RelocationEngine, state: RelocationState) -> None:
    plan, job = state.plan, state.plan.job
    claim = next(
        (c for c in engine.ledger.claims if c.claim_id == "relocation:" + job.job_id), None
    )
    if claim is None or not exact(
        (claim.claim_id, claim.job_id, claim.container_id, claim.whole_hu),
        ("relocation:" + job.job_id, job.job_id, job.hu_id, True),
    ):
        raise RuntimeError("RELOCATION_EXACT_CLAIM_CHANGED")
    if (
        type(claim.unit_ids) is not tuple
        or any(type(u) is not str for u in claim.unit_ids)
        or tuple(sorted(claim.unit_ids)) != tuple(sorted(plan.unit_ids))
    ):
        raise RuntimeError("RELOCATION_EXACT_CLAIM_CHANGED")


def _custody(engine: RelocationEngine, state: RelocationState) -> None:
    plan, job = state.plan, state.plan.job
    if any(
        s.spec.hu_id == job.hu_id and s.admitted_tick is not None
        for s in engine.whole_orders.values()
    ):
        if state.returned_tick is None:
            raise RuntimeError("RELOCATION_HU_ASSIGNED_TO_TWO_JOBS")
        return  # Existing whole validator proves every later completed custody transition.
    contents = engine.ledger.contents(job.hu_id)
    owner = (
        job.to_slot_id
        if state.placed_tick is not None
        else ("actor:" + job.actor_id if state.taken_tick is not None else job.from_slot_id)
    )
    if contents.container.owner_id != owner:
        raise RuntimeError("RELOCATION_CUSTODY_PRECEDES_COMPLETED_HANDLING")
    if (
        contents.container.recipe,
        {u.token.unit_id for u in contents.units},
        contents.gross_mass_kg,
    ) != (
        plan.cargo,
        set(plan.unit_ids),
        plan.gross_mass_kg,
    ):
        raise RuntimeError("RELOCATION_INTACT_CONTENTS_CHANGED")
    if any(
        c.owner_id == job.to_slot_id and c.container_id != job.hu_id
        for c in engine.ledger.snapshot().containers
    ):
        raise RuntimeError("RELOCATION_RESERVED_DESTINATION_OCCUPIED")


def check_world(engine: RelocationEngine) -> None:
    check_runtime(engine)
    LightFlowEngine._check(engine)
    engine._check_shipped_capacity()
    active = {
        s.plan.job.hu_id: s for s in engine.relocations.values() if s.admitted_tick is not None
    }
    # Only proved relocation custody replaces the stale anchor of an unadmitted whole job.
    whole = {
        k: s
        for k, s in engine.whole_orders.items()
        if s.spec.hu_id not in active or s.admitted_tick is not None
    }
    owners, claims = check_whole_world(
        whole,
        engine.whole_ports,
        engine.whole_sources,
        engine.workers,
        engine.leases,
        engine.ledger,
        engine.tick,
        frozenset(
            s.offer.definition.hu_id for s in engine.receipts.values() if s.placed_tick is None
        ),
    )
    for hu, state in active.items():
        if hu not in owners:
            owners[hu] = engine.ledger.contents(hu).container.owner_id
        if state.returned_tick is None:
            claims |= {"relocation:" + state.plan.job.job_id}
    check_receipt_world(
        engine.receipt_profile,
        engine.receipts,
        engine.workers,
        engine.leases,
        engine.ledger,
        engine.orders,
        engine.pick_claims,
        engine.tick,
        whole_owners=owners,
        whole_claims=claims,
    )
    check_roles(engine)
    check_packing(engine)
    check_units(engine)
    if engine.coordinator.unit_resources is not None:
        check_shipping(engine)
