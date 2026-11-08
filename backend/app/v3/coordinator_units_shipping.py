"""One terminal-capacity authority covers whole-HU and parcel port reservations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.v3.coordinator_events import unit_event

if TYPE_CHECKING:
    from app.v3.coordinator_engine import CoordinatorEngine


def terminal_resource(engine: CoordinatorEngine, key: str) -> str:
    return "port:" + engine._flow_for_order(key).port.port_id


def parcel_reservations(engine: CoordinatorEngine, owner: str) -> int:
    return sum(
        profile.shipped_owner == owner and engine.leases.get("port:" + profile.port.port_id) == key
        for key, profile in engine.unit_profiles.items()
    )


def reserve(engine: CoordinatorEngine, key: str) -> None:
    resource = terminal_resource(engine, key)
    if engine.leases.get(resource) != key:
        raise RuntimeError("PARCEL_CAPACITY_PROMISE_HAS_NO_ACTUAL_PORT_LEASE")
    worker = engine.workers[engine._flow_for_order(key).shipper_id]
    unit_event(engine, "parcel_capacity_reserved", key, worker=worker, resources=(resource,))


def release(engine: CoordinatorEngine, key: str) -> None:
    resource = terminal_resource(engine, key)
    if engine.leases.get(resource) == key:
        raise RuntimeError("COMMITTED_PARCEL_STILL_HOLDS_PORT_CAPACITY_PROMISE")
    worker = engine.workers[engine._flow_for_order(key).shipper_id]
    unit_event(engine, "parcel_capacity_committed", key, worker=worker, resources=(resource,))


def check_shipping(engine: CoordinatorEngine) -> None:
    expected = {}
    for key in engine.unit_states:
        p = engine._flow_for_order(key)
        worker = engine.workers[p.shipper_id]
        op = worker.operation
        if op is not None and op.order_id == key and op.kind == "shipping_service":
            if (
                worker.task != "shipper"
                or worker.order_id != key
                or worker.node != p.port.node
                or op.source_node != p.port.node
                or op.target_node != p.port.node
                or op.planned_end_tick - op.start_tick != p.port.service_tick
                or engine.leases.get("port:" + p.port.port_id) != key
            ):
                raise RuntimeError("PARCEL_SERVICE_PHYSICAL_ASSIGNMENT_MISMATCH")
            expected[terminal_resource(engine, key)] = key
    actual = {
        k: v for k, v in engine.leases.items() if k.startswith("port:") and v in engine.orders
    }
    if actual != expected:
        raise RuntimeError("PARCEL_PORT_PROMISE_DIFFERS_FROM_ACTUAL_SERVICE")
