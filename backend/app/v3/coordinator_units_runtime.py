"""Completed unit handling facts and staged cart release on the existing shared clock."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.v3.coordinator_events import unit_event
from app.v3.coordinator_units import picking_steps
from app.v3.coordinator_units_state import UnitState
from app.v3.light_flow_state import HumanState, HumanStep, OrderState

if TYPE_CHECKING:
    from app.v3.coordinator_engine import CoordinatorEngine


def admit(engine: CoordinatorEngine, order: OrderState) -> None:
    resources = engine.coordinator.unit_resources
    if resources is None:
        return
    key = order.spec.order_id
    profile = engine._flow_for_order(key)
    cart = next(c for c in resources.carts if c.cart.cart_id == profile.cart.cart_id)
    engine.unit_states[key] = UnitState(key, tuple(picking_steps(profile, cart.release_tick)))


def completed(engine: CoordinatorEngine, worker: HumanState, kind: str) -> None:
    key = str(worker.order_id)
    if key not in engine.unit_states:
        return
    if engine.workers.get(worker.spec.actor_id) is not worker:
        raise RuntimeError("COMPLETED_ACTOR_IS_NOT_ACTUAL_ENGINE_WORKER")
    state = engine.unit_states[key]
    profile = engine._flow_for_order(key)
    if worker.task == "picker":
        if worker.spec.actor_id != profile.picker_id:
            raise RuntimeError("COMPLETED_PICKER_ACTOR_DIFFERS_FROM_DECLARED_PLAN")
        _completed_step(state.picker_steps, state.completed_picker_steps, kind, "PICKER")
        state.completed_picker_steps += 1
        if kind == "pick":
            state.picked_tick = engine.tick
        elif kind == "deposit":
            state.deposited_tick = engine.tick
    elif worker.task == "shipper":
        if worker.spec.actor_id != profile.shipper_id:
            raise RuntimeError("COMPLETED_SHIPPER_ACTOR_DIFFERS_FROM_DECLARED_PLAN")
        _completed_step(state.shipper_steps, state.completed_shipper_steps, kind, "SHIPPER")
        state.completed_shipper_steps += 1
        if kind == "pickup_package":
            state.collected_tick = engine.tick


def _completed_step(steps: tuple[HumanStep, ...], count: int, kind: str, role: str) -> None:
    if type(count) is not int or not 0 <= count < len(steps):
        raise RuntimeError(f"INVALID_COMPLETED_{role}_STEP_COUNT")
    if steps[count].kind != kind:
        raise RuntimeError(f"COMPLETED_{role}_STEP_DIFFERS_FROM_DECLARED_PLAN")


def finish_picker(engine: CoordinatorEngine, worker: HumanState) -> bool:
    if engine.coordinator.unit_resources is None or worker.task != "picker":
        return False
    key = str(worker.order_id)
    state = engine.unit_states[key]
    if state.cart_released_tick is None and (
        not worker.steps or worker.steps[0].kind == "picker_return"
    ):
        _release_cart(engine, state, worker)
    if not worker.steps:
        state.picker_returned_tick = engine.tick
        worker.stop_waiting(engine.tick)
        worker.order_id, worker.task = None, "idle"
        unit_event(engine, "picker_returned", key, worker=worker)
    return True


def _release_cart(engine: CoordinatorEngine, state: UnitState, worker: HumanState) -> None:
    profile = engine._flow_for_order(state.order_id)
    cart = engine.carts[profile.cart.cart_id]
    resource = engine._cart_resource(cart.spec.cart_id)
    if (
        engine.leases.get(resource) != state.order_id
        or cart.node != cart.spec.home
        or cart.operation is not None
        or worker.node != cart.spec.home
    ):
        raise RuntimeError("CART_RELEASE_PRECEDES_ACTUAL_RETURN_OR_HANDLING")
    del engine.leases[resource]
    state.cart_released_tick = engine.tick
    unit_event(engine, "cart_released", state.order_id, worker=worker, resources=(resource,))


def finish_shipper(engine: CoordinatorEngine, worker: HumanState) -> bool:
    if engine.coordinator.unit_resources is None or worker.task != "shipper":
        return False
    if not worker.steps:
        key = str(worker.order_id)
        engine.unit_states[key].shipper_returned_tick = engine.tick
        worker.stop_waiting(engine.tick)
        worker.order_id, worker.task = None, "idle"
        unit_event(engine, "parcel_shipper_returned", key, worker=worker)
    return True
