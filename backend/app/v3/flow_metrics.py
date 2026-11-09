"""Settled SMALL-flow business metrics; paid return remains resource exposure."""

from typing import Any

from app.v3.execution_types import ACTOR_IDS
from app.v3.flow_metrics_resources import resource_waits, resources
from app.v3.light_flow_models import FlowOutcome, FlowProfile, FlowSnapshot
from app.v3.manual_metrics import cycle_statistics
from app.v3.runtime_time import TICKS_PER_SECOND


def _validate(profile: FlowProfile, snapshot: FlowSnapshot) -> None:
    if type(snapshot.tick) is not int or snapshot.tick < 0:
        raise ValueError("metric observation needs a nonnegative integer tick")
    if {a.actor_id for a in profile.actors} != set(ACTOR_IDS) or len(profile.actors) != 24:
        raise ValueError("metric profile needs the unchanged 24 actor identities")
    if {w.actor_id for w in snapshot.workers} != set(ACTOR_IDS) or len(snapshot.workers) != 24:
        raise ValueError("metric worker observation identities differ from profile")
    orders = {order.order_id: order for order in profile.orders}
    if len(orders) != len(profile.orders) or len(snapshot.orders) != len(orders):
        raise ValueError("metric order observation identities differ from profile")
    if {view.order_id for view in snapshot.orders} != set(orders):
        raise ValueError("metric order observation identities differ from profile")
    for view in snapshot.orders:
        arrival = orders[view.order_id].arrival_tick
        if any(
            type(t) is not int or not arrival <= t <= snapshot.tick
            for t in (view.admitted_tick, view.shipped_tick)
            if t is not None
        ):
            raise ValueError("metric order transition is outside the observed window")
        if view.shipped_tick is not None and (
            view.admitted_tick is None or view.shipped_tick < view.admitted_tick
        ):
            raise ValueError("shipment must follow observed admission")
    for worker in snapshot.workers:
        values = worker.paid_ticks, worker.queue_ticks
        if (
            any(type(value) is not int or value < 0 for value in values)
            or sum(values) > snapshot.tick
        ):
            raise ValueError("invalid paid/wait worker exposure")
    if (
        type(snapshot.belt.tick) is not int
        or snapshot.belt.tick != snapshot.tick
        or type(snapshot.belt.queue_ticks) is not int
        or snapshot.belt.queue_ticks < 0
        or (snapshot.tick == 0 and snapshot.belt.queue_ticks != 0)
    ):
        raise ValueError("invalid stopped-carrier exposure observation")


def _business(profile: FlowProfile, snapshot: FlowSnapshot) -> dict[str, Any]:
    orders = {order.order_id: order for order in profile.orders}
    arrived = [order for order in profile.orders if order.arrival_tick <= snapshot.tick]
    completed = {
        view.order_id: view.shipped_tick
        for view in snapshot.orders
        if view.shipped_tick is not None
    }
    cycles = tuple(tick - orders[identity].arrival_tick for identity, tick in completed.items())
    return {
        "arrived_orders": len(arrived),
        "completed_orders": len(completed),
        "backlog_orders": len(arrived) - len(completed),
        "completed_units": sum(len(orders[identity].package_placements) for identity in completed),
        **cycle_statistics(cycles),
    }


def _order_queues(profile: FlowProfile, snapshot: FlowSnapshot) -> dict[str, float | None]:
    orders = {order.order_id: order for order in profile.orders}
    unadmitted = unfinished = 0
    for view in snapshot.orders:
        arrival = orders[view.order_id].arrival_tick
        if arrival > snapshot.tick:
            continue
        admitted = snapshot.tick if view.admitted_tick is None else view.admitted_tick
        shipped = snapshot.tick if view.shipped_tick is None else view.shipped_tick
        unadmitted += admitted - arrival
        unfinished += shipped - arrival
    return {
        "unadmitted_order_seconds": unadmitted / TICKS_PER_SECOND,
        "mean_unadmitted_orders": unadmitted / snapshot.tick if snapshot.tick else None,
        "unfinished_order_seconds": unfinished / TICKS_PER_SECOND,
        "mean_unfinished_orders": unfinished / snapshot.tick if snapshot.tick else None,
    }


def _window(profile: FlowProfile, snapshot: FlowSnapshot) -> dict[str, Any]:
    _validate(profile, snapshot)
    return {
        "tick": snapshot.tick,
        "time_s": snapshot.tick / TICKS_PER_SECOND,
        **_business(profile, snapshot),
        **resources(snapshot),
        "queues": {**_order_queues(profile, snapshot), **resource_waits(snapshot)},
    }


def summary(profile: FlowProfile, outcome: FlowOutcome) -> dict[str, Any]:
    horizon = _window(profile, outcome.at_horizon)
    return {
        "metrics_version": "qoima-light-flow-metrics-v1",
        "counts_boundary": "settled_tick_inclusive",
        "integral_window": "[0,T)",
        "cycle_completion": "outbound_business_handover",
        "role_basis": "fixed_source_roster",
        "backlog_at_horizon": horizon["backlog_orders"],
        "at_horizon": horizon,
        "at_end": _window(profile, outcome.at_end),
    }
