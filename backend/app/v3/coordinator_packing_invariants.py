"""Packing reservations, real human work and cargo custody must agree at every settled tick."""

from __future__ import annotations

from fractions import Fraction
from typing import TYPE_CHECKING

from app.v3.belt_geometry import footprint, requirements
from app.v3.conveyor_models import ConveyorPayload
from app.v3.coordinator_packing_admission import ownership_resources
from app.v3.coordinator_packing_models import PackingState, UnitContext
from app.v3.coordinator_validation import role_route

if TYPE_CHECKING:
    from app.v3.coordinator_engine import CoordinatorEngine


def check_packing(engine: CoordinatorEngine) -> None:
    expected: dict[str, str] = {}
    _contexts(engine)
    for state in engine.packing_states.values():
        _ticks(engine, state)
        resources = ownership_resources(engine, state.order_id, state.actor_id)
        if state.engine_resources != resources:
            raise RuntimeError("PACK_DECLARED_RESOURCES_DIFFER_FROM_ACTUAL_BINDING")
        for key in state.held_resources():
            if key in expected:
                raise RuntimeError("PACK_RESOURCE_HAS_TWO_ASSIGNMENTS")
            expected[key] = state.order_id
        if state.phase != "complete":
            _worker(engine, state)
        if state.cleared_tick is None:
            _local_footprint(engine, state)
        _custody(engine, state)
    if {k: v for k, v in engine.leases.items() if k.startswith("pack:")} != expected:
        raise RuntimeError("PACK_PHYSICAL_RESERVATION_MISMATCH")
    _owner_capacity(engine)


def _contexts(engine: CoordinatorEngine) -> None:
    admitted = {k for k, order in engine.orders.items() if order.admitted_tick is not None}
    if set(engine.unit_contexts) != admitted or not engine.packing_states.keys() <= admitted:
        raise RuntimeError("PACK_ORDER_CONTEXT_DOES_NOT_MATCH_ACTUAL_ADMISSION")
    for key, context in engine.unit_contexts.items():
        profile = engine._flow_for_order(key)
        expected = UnitContext(
            key,
            profile.picker_id,
            profile.cart.cart_id,
            profile.station.station_id,
            profile.shipper_id,
            engine.orders[key].spec.source_node,
            profile.intake_node,
            profile.output_node,
            profile.port.port_id,
        )
        if context != expected:
            raise RuntimeError("PACK_ORDER_CONTEXT_BINDING_CHANGED")


def _ticks(engine: CoordinatorEngine, state: PackingState) -> None:
    counts = {
        "approach": 0,
        "ready": 0,
        "pack": 0,
        "packed": 1,
        "clear": 1,
        "returning": 2,
        "complete": 3,
    }
    count = counts.get(state.phase)
    values = (state.packed_tick, state.cleared_tick, state.released_tick)
    if count is None or any(
        (value is None) != (index >= count) for index, value in enumerate(values)
    ):
        raise RuntimeError("PACK_PHASE_TIMESTAMP_MISMATCH")
    previous = 0
    for value in (state.assigned_tick, *values[:count]):
        if type(value) is not int or not previous <= value <= engine.tick:
            raise RuntimeError("PACK_INVALID_ACTUAL_COMPLETION_TICK")
        previous = value


def _worker(engine: CoordinatorEngine, state: PackingState) -> None:
    profile = engine._flow_for_order(state.order_id)
    worker = engine.workers[state.actor_id]
    if worker.order_id != state.order_id or state.station_id != profile.station.station_id:
        raise RuntimeError("PACK_ASSIGNED_WORKER_OR_STATION_MISMATCH")
    if state.role_intent_id is not None:
        role = engine.role_states[state.role_intent_id]
        if (
            role.status not in {"active", "return_wait"}
            or role.intent.actor_id != state.actor_id
            or engine.station_bindings.get(state.station_id) != state.actor_id
        ):
            raise RuntimeError("PACK_HELPER_NO_LONGER_OWNS_ACTUAL_ROLE")
    elif state.actor_id != profile.packer_id:
        raise RuntimeError("PACK_UNKNOWN_PRIMARY_ASSIGNMENT")
    if state.phase in {"approach", "returning"}:
        _travel(engine, state)
        return
    if worker.node != profile.station.node or worker.steps or worker.task != "station":
        raise RuntimeError("PACK_LOCAL_ACTOR_TELEPORT_OR_TASK_MISMATCH")
    if state.phase in {"pack", "clear"}:
        carrier = next(c for c in engine.belt.states if c.job.job_id == state.order_id)
        operation = worker.operation
        if (
            operation is None
            or carrier.active is None
            or operation.kind != state.phase
            or operation.route is not None
            or operation.order_id != state.order_id
            or operation.start_tick != carrier.active.start_tick
            or operation.planned_end_tick != carrier.active.planned_end_tick
            or operation.source_node != worker.node
            or operation.target_node != worker.node
            or worker.waiting_since is not None
        ):
            raise RuntimeError("PACK_ACTUAL_LOCAL_OPERATION_MISMATCH")
    elif worker.operation is not None:
        raise RuntimeError("PACK_OPERATION_EXISTS_OUTSIDE_PAID_PHASE")


def _travel(engine: CoordinatorEngine, state: PackingState) -> None:
    profile = engine._flow_for_order(state.order_id)
    worker = engine.workers[state.actor_id]
    operation = worker.operation
    target = worker.spec.home if state.phase == "returning" else profile.station.node
    start = profile.station.node if state.phase == "returning" else state.assigned_node
    duration, route = role_route(engine.coordinator, state.actor_id, start, target)
    expected_kind = "return" if state.phase == "returning" else "travel_empty"
    if (
        operation is None
        or worker.node is not None
        or len(worker.steps) != 1
        or operation.kind != expected_kind
        or operation.source_node != start
        or operation.target_node != target
        or operation.route != route
        or operation.planned_end_tick != operation.start_tick + duration
        or not operation.start_tick <= engine.tick < operation.planned_end_tick
        or operation.cart_id is not None
        or operation.carrying_id is not None
    ):
        raise RuntimeError("PACK_PAID_TRAVEL_MISMATCH")


def _local_footprint(engine: CoordinatorEngine, state: PackingState) -> None:
    carrier = next(c for c in engine.belt.states if c.job.job_id == state.order_id)
    if carrier.pose is None:
        raise RuntimeError("PACK_LOCAL_RESERVATION_HAS_NO_ACTUAL_POSE")
    engine.belt._replacement_steps(carrier, state.parcel)
    pack_index, clear_index = engine.belt.stage_indices[state.order_id]
    target = requirements(
        engine.belt.source, footprint(engine.belt.source, state.parcel, carrier.pose)
    )
    required = target | carrier.steps[pack_index].resources | carrier.steps[clear_index].resources
    if state.belt_resources != required or any(
        engine.belt.external.get(key) != state.order_id for key in required
    ):
        raise RuntimeError("PACK_CLEAR_FOOTPRINT_RESERVATION_LOST")


def _custody(engine: CoordinatorEngine, state: PackingState) -> None:
    profile = engine._flow_for_order(state.order_id)
    order = engine.orders[state.order_id].spec
    carrier, package = (
        engine.ledger.contents(order.carrier_id),
        engine.ledger.contents(order.package_id),
    )
    if state.cleared_tick is not None:
        if carrier.container.owner_id != profile.station.empty_owner:
            raise RuntimeError("PACK_EMPTY_CARRIER_LEFT_PHYSICAL_RACK")
        return
    owner = (
        profile.package_pool_owner
        if state.phase in {"approach", "ready"}
        else profile.station.bench_owner
    )
    units = carrier.units if state.packed_tick is None else package.units
    expected_mass = package.container.recipe.tare_kg + sum(
        (u.token.recipe.gross_mass_kg for u in units), Fraction(0)
    )
    expected = ConveyorPayload(
        order.package_id,
        "sealed_parcel",
        package.container.recipe.outer,
        expected_mass,
        "upright_xyz",
        state.order_id,
        package.container.recipe.provenance,
    )
    if (
        carrier.container.owner_id != "belt:" + state.order_id
        or package.container.owner_id != owner
        or state.parcel != expected
        or {u.token.unit_id for u in units} != {p.unit_id for p in order.package_placements}
        or (state.packed_tick is not None and carrier.units)
        or (state.packed_tick is None and package.units)
    ):
        raise RuntimeError("PACK_CUSTODY_OR_PREDICTED_MASS_MISMATCH")


def _owner_capacity(engine: CoordinatorEngine) -> None:
    reserved: dict[str, set[str]] = {}
    for state in engine.packing_states.values():
        station = engine._flow_for_order(state.order_id).station
        order = engine.orders[state.order_id].spec
        for owner, material in (
            (station.bench_owner, order.package_id),
            (station.empty_owner, order.carrier_id),
        ):
            ids = reserved.setdefault(owner, set())
            if state.cleared_tick is None:
                ids.add(material)
    for owner, ids in reserved.items():
        ids.update(
            c.container_id for c in engine.ledger.snapshot().containers if c.owner_id == owner
        )
        capacity = next(o.capacity for o in engine.profile.owners if o.owner_id == owner)
        if len(ids) > capacity:
            raise RuntimeError("PACK_RESERVED_AND_ACTUAL_OWNER_CAPACITY_EXCEEDED")
