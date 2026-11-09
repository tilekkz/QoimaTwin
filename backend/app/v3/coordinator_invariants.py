"""Validate actual role ownership and paid routes at each settled shared tick."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.v3.coordinator_state import RoleState
from app.v3.coordinator_validation import role_route

if TYPE_CHECKING:
    from app.v3.coordinator_engine import CoordinatorEngine


def check_roles(engine: CoordinatorEngine) -> None:
    leases: dict[str, str] = {}
    stations: dict[str, str] = {}
    active_actors: set[str] = set()
    for state in engine.role_states.values():
        _ticks(engine, state)
        if state.status in {"unreleased", "quiescing", "restored", "rejected"}:
            continue
        actor, station = state.intent.actor_id, state.intent.station_id
        if actor in active_actors:
            raise RuntimeError("ROLE_ACTOR_ASSIGNED_TWICE")
        active_actors.add(actor)
        leases["staff:actor:" + actor] = state.intent.intent_id
        if state.status in {"outward", "active", "return_wait"}:
            if station in stations:
                raise RuntimeError("ROLE_STATION_ASSIGNED_TWICE")
            stations[station] = actor
            leases["staff:station:" + station] = state.intent.intent_id
        _physical(engine, state)
    actual = {key: value for key, value in engine.leases.items() if key.startswith("staff:")}
    if actual != leases or engine.station_bindings != stations:
        raise RuntimeError("ROLE_PHYSICAL_OWNERSHIP_MISMATCH")


def _ticks(engine: CoordinatorEngine, state: RoleState) -> None:
    phases = {
        "unreleased": 0,
        "quiescing": 0,
        "outward": 1,
        "active": 2,
        "return_wait": 2,
        "returning": 3,
        "restored": 4,
        "rejected": 0,
    }
    values = (
        state.departed_tick,
        state.activated_tick,
        state.return_started_tick,
        state.restored_tick,
    )
    count = phases.get(state.status)
    if count is None or any(
        (value is None) != (index >= count) for index, value in enumerate(values)
    ):
        raise RuntimeError("ROLE_PHASE_TIMESTAMP_MISMATCH")
    previous = state.intent.request_tick
    for value in values[:count]:
        if type(value) is not int or not previous <= value <= engine.tick:
            raise RuntimeError("ROLE_INVALID_ACTUAL_TICK")
        previous = value


def _physical(engine: CoordinatorEngine, state: RoleState) -> None:
    worker = engine.workers[state.intent.actor_id]
    if state.status in {"outward", "returning"}:
        _motion(engine, state)
    elif state.status in {"active", "return_wait"}:
        packing = engine.packing_states.get(str(worker.order_id))
        if (
            packing is not None
            and packing.actor_id == state.intent.actor_id
            and packing.phase != "complete"
        ):
            # Packing invariants verify the same physical worker, role lease and local footprint.
            return
        expected = engine.role_stations[state.intent.station_id].node_id
        if (
            worker.node != expected
            or worker.operation is not None
            or worker.steps
            or worker.order_id is not None
            or worker.waiting_since is not None
        ):
            raise RuntimeError("ROLE_ACTIVE_HELPER_NOT_AT_ASSIGNED_STATION")
    else:
        raise RuntimeError("ROLE_UNKNOWN_PHYSICAL_PHASE")


def _motion(engine: CoordinatorEngine, state: RoleState) -> None:
    worker = engine.workers[state.intent.actor_id]
    operation = worker.operation
    kind = "role_outward" if state.status == "outward" else "role_return"
    target = (
        engine.role_stations[state.intent.station_id].node_id
        if state.status == "outward"
        else state.intent.restore_node
    )
    if (
        worker.order_id != state.intent.intent_id
        or worker.task != kind
        or operation is None
        or len(worker.steps) != 1
        or worker.node is not None
        or worker.waiting_since is not None
    ):
        raise RuntimeError("ROLE_TRANSITION_WORKER_MISMATCH")
    duration, route = role_route(
        engine.coordinator, worker.spec.actor_id, operation.source_node, target
    )
    step = worker.steps[0]
    started = state.departed_tick if state.status == "outward" else state.return_started_tick
    if (
        operation.kind != kind
        or operation.order_id != state.intent.intent_id
        or operation.start_tick != started
        or operation.target_node != target
        or operation.route != route
        or operation.planned_end_tick != operation.start_tick + duration
        or not operation.start_tick <= engine.tick < operation.planned_end_tick
        or operation.carrying_id is not None
        or operation.cart_id is not None
        or step.kind != kind
        or step.target != target
        or step.duration != duration
        or step.route != route
        or step.carrying_id is not None
        or step.cart_id is not None
        or (operation.planned_end_tick, "human", worker.spec.actor_id) not in engine.pending
    ):
        raise RuntimeError("ROLE_PAID_MOTION_MISMATCH")
