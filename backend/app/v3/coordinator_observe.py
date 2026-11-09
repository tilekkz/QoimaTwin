"""Actual role observations and interval exposure without duplicating physical worker state."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.v3.coordinator_models import ActorRoleView, CoordinatorSnapshot, RoleExposure
from app.v3.coordinator_state import RoleState

if TYPE_CHECKING:
    from app.v3.coordinator_engine import CoordinatorEngine


def assignment(engine: CoordinatorEngine, actor: str) -> RoleState | None:
    return next(
        (
            s
            for s in engine.role_states.values()
            if s.intent.actor_id == actor and s.status not in {"unreleased", "restored", "rejected"}
        ),
        None,
    )


def available(engine: CoordinatorEngine, actor: str, tick: int) -> bool:
    return engine.workers[actor].spec.available_tick <= tick and not any(
        w.actor_id == actor and w.start_tick <= tick < w.end_tick
        for w in engine.coordinator.registry.unavailability
    )


def effective_role(engine: CoordinatorEngine, actor: str) -> str:
    state = assignment(engine, actor)
    if state is not None:
        if state.status in {"outward", "returning"}:
            return "transition"
        if state.status in {"active", "return_wait"}:
            return "pack"
    return engine.capabilities[actor].primary_role


def projected_exposure(engine: CoordinatorEngine, tick: int) -> dict[str, int]:
    values = dict(engine.role_totals)
    for actor in engine.workers:
        category = (
            effective_role(engine, actor)
            if available(engine, actor, engine.exposure_tick)
            else "unavailable"
        )
        values[category] += tick - engine.exposure_tick
    return values


def actor_roles(engine: CoordinatorEngine, tick: int) -> tuple[ActorRoleView, ...]:
    result = []
    for actor in sorted(engine.workers):
        state = assignment(engine, actor)
        result.append(
            ActorRoleView(
                actor,
                engine.capabilities[actor].primary_role,
                effective_role(engine, actor),
                available(engine, actor, tick),
                state.intent.intent_id if state else None,
            )
        )
    return tuple(result)


def snapshot(engine: CoordinatorEngine, base: object, tick: int) -> CoordinatorSnapshot:
    from app.v3.whole_flow_models import WholeFlowSnapshot

    if not isinstance(base, WholeFlowSnapshot):
        raise RuntimeError("COORDINATOR_REQUIRES_WHOLE_SNAPSHOT")
    values = projected_exposure(engine, tick)
    exposure = RoleExposure(
        tuple((r, values[r]) for r in engine.role_names),
        values["transition"],
        values["unavailable"],
    )
    return CoordinatorSnapshot(
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
        tuple(s.view() for _, s in sorted(engine.role_states.items())),
        actor_roles(engine, tick),
        tuple(sorted(engine.station_bindings.items())),
        exposure,
        tuple(value for _, value in sorted(engine.unit_contexts.items())),
        tuple(value.view() for _, value in sorted(engine.packing_states.items())),
        tuple(sorted(engine.packing_waits.items())),
        tuple(engine._cart_view(key) for key in sorted(engine.carts)),
        tuple(
            (key, state.cart_released_tick)
            for key, state in sorted(engine.unit_states.items())
            if state.cart_released_tick is not None
        ),
        tuple(state.view() for _, state in sorted(engine.unit_states.items())),
    )


def business_complete(engine: CoordinatorEngine) -> bool:
    return (
        all(o.shipped_tick is not None for o in engine.orders.values())
        and all(s.shipped_tick is not None for s in engine.whole_orders.values())
        and all(
            s.placed_tick is not None or s.offer.arrival_tick >= engine.horizon
            for s in engine.receipts.values()
        )
    )


def resources_idle(engine: CoordinatorEngine) -> bool:
    return (
        not engine.leases
        and not engine.station_bindings
        and all(
            w.order_id is None and w.operation is None and not w.steps and w.waiting_since is None
            for w in engine.workers.values()
        )
        and all(s.complete for s in engine.belt.states)
    )
