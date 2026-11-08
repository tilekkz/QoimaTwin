"""The exact admitted context binds carts, picker plans, custody and original units."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.v3.coordinator_units_state import UnitState

if TYPE_CHECKING:
    from app.v3.coordinator_engine import CoordinatorEngine


def check_units(engine: CoordinatorEngine) -> None:
    resources = engine.coordinator.unit_resources
    if resources is None:
        return
    declared = {c.cart.cart_id: c.cart for c in resources.carts}
    if set(engine.carts) != set(declared) or any(
        cart.spec is not declared[key] for key, cart in engine.carts.items()
    ):
        raise RuntimeError("CART_SPEC_OR_REGISTRY_DRIFT")
    if set(engine.unit_states) != set(engine.unit_contexts):
        raise RuntimeError("UNIT_PROGRESS_DIFFERS_FROM_ACTUAL_ADMISSION")
    reserved: dict[str, str] = {}
    for key, state in engine.unit_states.items():
        profile = engine._flow_for_order(key)
        _progress(engine, state)
        _picker(engine, state)
        _shipper(engine, state)
        _custody(engine, state)
        if state.cart_released_tick is None:
            resource = engine._cart_resource(profile.cart.cart_id)
            if resource in reserved:
                raise RuntimeError("CART_HAS_TWO_ADMITTED_JOBS")
            reserved[resource] = key
            _cart(engine, state)
    if {k: v for k, v in engine.leases.items() if k.startswith("cart:")} != reserved:
        raise RuntimeError("CART_ASSIGNMENT_LEASE_MISMATCH")
    for key, cart in engine.carts.items():
        if engine._cart_resource(key) not in reserved and (
            cart.node != cart.spec.home or cart.operation is not None
        ):
            raise RuntimeError("RELEASED_CART_HAS_NOT_PHYSICALLY_RETURNED")


def _progress(engine: CoordinatorEngine, state: UnitState) -> None:
    admitted = engine.orders[state.order_id].admitted_tick
    if type(admitted) is not int:
        raise RuntimeError("UNIT_PROGRESS_HAS_NO_ACTUAL_ADMISSION")
    _chain(
        (
            state.picked_tick,
            state.deposited_tick,
            state.cart_released_tick,
            state.picker_returned_tick,
        ),
        admitted,
        engine.tick,
    )
    _chain(
        (
            state.collected_tick,
            engine.orders[state.order_id].shipped_tick,
            state.shipper_returned_tick,
        ),
        admitted,
        engine.tick,
    )


def _chain(values: tuple[int | None, ...], start: int, end: int) -> None:
    pending = False
    for value in values:
        if value is None:
            pending = True
        elif type(value) is not int or pending or not start <= value <= end:
            raise RuntimeError("UNIT_PROGRESS_REQUIRES_EXACT_COMPLETED_ORDERED_TICKS")
        else:
            start = value


def _picker(engine: CoordinatorEngine, state: UnitState) -> None:
    profile = engine._flow_for_order(state.order_id)
    worker = engine.workers[profile.picker_id]
    count = state.completed_picker_steps
    if type(count) is not int or not 0 <= count <= len(state.picker_steps):
        raise RuntimeError("INVALID_COMPLETED_PICKER_STEP_COUNT")
    if state.picker_returned_tick is not None:
        if count != len(state.picker_steps) or state.cart_released_tick is None:
            raise RuntimeError("PICKER_RETURNED_WITH_UNFINISHED_PHYSICAL_WORK")
        return
    remaining = state.picker_steps[count:]
    if (
        worker.order_id != state.order_id
        or worker.task != "picker"
        or tuple(worker.steps) != remaining
    ):
        raise RuntimeError("PICKER_ACTUAL_ASSIGNMENT_OR_PLAN_MISMATCH")
    op = worker.operation
    if op is not None:
        step = remaining[0]
        if (
            op.order_id != state.order_id
            or op.kind != step.kind
            or op.route is not step.route
            or op.target_node != step.target
            or op.cart_id != step.cart_id
            or op.carrying_id != step.carrying_id
            or op.planned_end_tick - op.start_tick != step.duration
            or not op.start_tick <= engine.tick < op.planned_end_tick
        ):
            raise RuntimeError("PICKER_OPERATION_DIFFERS_FROM_ACTUAL_PLAN")


def _cart(engine: CoordinatorEngine, state: UnitState) -> None:
    profile = engine._flow_for_order(state.order_id)
    worker, cart = engine.workers[profile.picker_id], engine.carts[profile.cart.cart_id]
    operation = worker.operation
    attached = operation is not None and operation.cart_id == cart.spec.cart_id
    expected = profile.cart.home
    for step in state.picker_steps[: state.completed_picker_steps]:
        if step.cart_id is not None:
            expected = step.target
    if attached:
        assert operation is not None
        node = None if operation.route is not None else operation.source_node
        if cart.operation is not operation or cart.node != node:
            raise RuntimeError("CART_MOTION_NOT_OWNED_BY_ACTUAL_PICKER")
    elif cart.operation is not None or cart.node != expected:
        raise RuntimeError("PARKED_CART_LEFT_ITS_LAST_COMPLETED_POSITION")


def _custody(engine: CoordinatorEngine, state: UnitState) -> None:
    p, order = engine._flow_for_order(state.order_id), engine.orders[state.order_id].spec
    carrier_owner = p.carrier_pool_owner
    for step in state.picker_steps[: state.completed_picker_steps]:
        if step.kind in {"attach", "source_attach"}:
            carrier_owner = p.cart.owner_id
        elif step.kind in {"detach", "source_detach"}:
            carrier_owner = "actor:" + p.picker_id
        elif step.kind == "deposit":
            carrier_owner = "belt:" + state.order_id
    packing = engine.packing_states.get(state.order_id)
    if packing is not None and packing.cleared_tick is not None:
        carrier_owner = p.station.empty_owner
    if engine.ledger.contents(order.carrier_id).container.owner_id != carrier_owner:
        raise RuntimeError("UNIT_CARRIER_CUSTODY_HAS_NO_COMPLETED_PHYSICAL_HANDOFF")
    _package(engine, state)
    unit_owner = order.source_hu if state.picked_tick is None else order.carrier_id
    if packing is not None and packing.packed_tick is not None:
        unit_owner = order.package_id
    contents = {u.token.unit_id for u in engine.ledger.contents(unit_owner).units}
    if not {p.unit_id for p in order.carrier_placements} <= contents:
        raise RuntimeError("ADMITTED_ORIGINAL_UNITS_LEFT_ACTUAL_CUSTODY")


def _package(engine: CoordinatorEngine, state: UnitState) -> None:
    p = engine._flow_for_order(state.order_id)
    owner = p.package_pool_owner
    packing = engine.packing_states.get(state.order_id)
    if packing is not None and packing.phase not in {"approach", "ready"}:
        owner = p.station.bench_owner
    if packing is not None and packing.cleared_tick is not None:
        owner = "belt:" + state.order_id
    if state.collected_tick is not None:
        owner = "actor:" + p.shipper_id
    if engine.orders[state.order_id].shipped_tick is not None:
        owner = p.shipped_owner
    order = engine.orders[state.order_id].spec
    if engine.ledger.contents(order.package_id).container.owner_id != owner:
        raise RuntimeError("UNIT_PACKAGE_CUSTODY_HAS_NO_COMPLETED_PHYSICAL_HANDOFF")


def _shipper(engine: CoordinatorEngine, state: UnitState) -> None:
    if not state.shipper_steps:
        if state.collected_tick is not None or state.shipper_returned_tick is not None:
            raise RuntimeError("PARCEL_HANDOFF_WITHOUT_ASSIGNED_SHIPPER")
        return
    count = state.completed_shipper_steps
    if type(count) is not int or not 0 <= count <= len(state.shipper_steps):
        raise RuntimeError("INVALID_COMPLETED_SHIPPER_STEP_COUNT")
    if state.shipper_returned_tick is not None:
        if count != len(state.shipper_steps) or engine.orders[state.order_id].shipped_tick is None:
            raise RuntimeError("PARCEL_SHIPPER_RETURNED_BEFORE_COMPLETE_PHYSICAL_WORK")
        return
    worker = engine.workers[engine._flow_for_order(state.order_id).shipper_id]
    remaining = state.shipper_steps[count:]
    if (
        worker.order_id != state.order_id
        or worker.task != "shipper"
        or tuple(worker.steps) != remaining
    ):
        raise RuntimeError("SHIPPER_ACTUAL_ASSIGNMENT_OR_PLAN_MISMATCH")
    op = worker.operation
    if op is not None:
        step = remaining[0]
        if (
            op.order_id != state.order_id
            or op.kind != step.kind
            or op.route is not step.route
            or op.target_node != step.target
            or op.cart_id is not None
            or op.carrying_id != step.carrying_id
            or op.planned_end_tick - op.start_tick != step.duration
            or not op.start_tick <= engine.tick < op.planned_end_tick
        ):
            raise RuntimeError("SHIPPER_OPERATION_DIFFERS_FROM_ACTUAL_PLAN")
