"""Actual paid role transitions reuse the connected worker map, routes, heap and leases."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.v3.coordinator_observe import available
from app.v3.coordinator_state import RoleState
from app.v3.coordinator_validation import role_route
from app.v3.light_flow_state import HumanState, HumanStep

if TYPE_CHECKING:
    from app.v3.coordinator_engine import CoordinatorEngine


def clean(engine: CoordinatorEngine, worker: HumanState) -> bool:
    if (
        worker.order_id is not None
        or worker.operation is not None
        or worker.steps
        or worker.waiting_since is not None
    ):
        return False
    actor = worker.spec.actor_id
    if any(c.owner_id == "actor:" + actor for c in engine.ledger.snapshot().containers):
        return False
    if any(r in engine.leases for r in ("receipt:worker:" + actor, "whole:worker:" + actor)):
        return False
    return not any(
        engine.leases.get(engine._cart_resource(c.cart_id)) in engine.unit_contexts
        and engine.unit_contexts[engine.leases[engine._cart_resource(c.cart_id)]].picker_id == actor
        for c in engine._cart_specs()
    )


def station_free(engine: CoordinatorEngine, state: RoleState) -> bool:
    station = engine.role_stations[state.intent.station_id]
    if station.station_id in engine.station_bindings:
        return False
    primary = engine.primary_bindings[station.station_id]
    if not clean(engine, engine.workers[primary]) or available(engine, primary, engine.tick):
        return False
    return not any(c.owner_id == station.bench_owner for c in engine.ledger.snapshot().containers)


def dispatch(engine: CoordinatorEngine) -> None:
    for state in sorted(
        engine.role_states.values(), key=lambda s: (s.intent.request_tick, s.intent.intent_id)
    ):
        worker = engine.workers[state.intent.actor_id]
        if state.status == "quiescing" and clean(engine, worker):
            _depart(engine, state, worker)
        elif state.status in {"active", "return_wait"} and engine.tick >= state.intent.return_tick:
            if clean(engine, worker):
                _return(engine, state, worker)
            elif state.status != "return_wait":
                state.status = "return_wait"
                engine._staff_event("role_return_waiting", state, worker=worker)


def _depart(engine: CoordinatorEngine, state: RoleState, worker: HumanState) -> None:
    if worker.node is None or not available(engine, state.intent.actor_id, engine.tick):
        return
    station = engine.role_stations[state.intent.station_id]
    outward, route = role_route(
        engine.coordinator, state.intent.actor_id, worker.node, station.node_id
    )
    returning, _ = role_route(
        engine.coordinator, state.intent.actor_id, station.node_id, state.intent.restore_node
    )
    if (
        engine.tick + outward > state.intent.return_tick
        or state.intent.return_tick + returning > state.intent.restore_by_tick
    ):
        reject(engine, state, "ROLE_WINDOW_TOO_SHORT")
        return
    if not station_free(engine, state):
        return
    engine.station_bindings[station.station_id] = state.intent.actor_id
    engine.leases["staff:station:" + station.station_id] = state.intent.intent_id
    engine.leases["staff:actor:" + state.intent.actor_id] = state.intent.intent_id
    state.status, state.departed_tick = "outward", engine.tick
    _assign(engine, state, worker, HumanStep("role_outward", station.node_id, outward, route))


def _return(engine: CoordinatorEngine, state: RoleState, worker: HumanState) -> None:
    if worker.node is None:
        raise RuntimeError("ROLE_RETURN_HAS_NO_ACTUAL_NODE")
    duration, route = role_route(
        engine.coordinator, state.intent.actor_id, worker.node, state.intent.restore_node
    )
    del engine.station_bindings[state.intent.station_id]
    del engine.leases["staff:station:" + state.intent.station_id]
    state.status, state.return_started_tick = "returning", engine.tick
    _assign(
        engine, state, worker, HumanStep("role_return", state.intent.restore_node, duration, route)
    )


def _assign(
    engine: CoordinatorEngine, state: RoleState, worker: HumanState, step: HumanStep
) -> None:
    worker.order_id, worker.task, worker.steps, worker.waiting_since = (
        state.intent.intent_id,
        step.kind,
        [step],
        engine.tick,
    )
    engine._staff_event("role_transition_assigned", state, worker=worker)
    engine._start_step(worker)


def finished(engine: CoordinatorEngine, worker: HumanState) -> None:
    if worker.steps:
        return
    state = engine.role_states[str(worker.order_id)]
    if worker.task == "role_outward":
        expected = engine.role_stations[state.intent.station_id].node_id
        state.status, state.activated_tick = "active", engine.tick
        event = "role_activated"
    else:
        expected = state.intent.restore_node
        state.status, state.restored_tick = "restored", engine.tick
        del engine.leases["staff:actor:" + state.intent.actor_id]
        event = "role_restored"
    if worker.node != expected:
        raise RuntimeError("ROLE_COMPLETION_DID_NOT_REACH_REAL_NODE")
    worker.stop_waiting(engine.tick)
    worker.order_id, worker.task = None, "idle"
    engine._staff_event(event, state, worker=worker)


def reject(engine: CoordinatorEngine, state: RoleState, reason: str) -> None:
    state.status, state.reason = "rejected", reason
    engine._violation(state.intent.actor_id, reason, state.intent.intent_id)
    engine._staff_event("role_rejected", state)
