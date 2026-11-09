"""Actual actor-bound pack and clear callbacks on the one existing FlowBelt clock."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from app.v3.belt_state import RunningCarrier
from app.v3.coordinator_packing_admission import reserve_actor
from app.v3.coordinator_packing_models import PackingState, UnitContext
from app.v3.light_flow_plan import travel
from app.v3.light_flow_state import HumanState, HumanStep, OrderState

if TYPE_CHECKING:
    from app.v3.coordinator_engine import CoordinatorEngine


def bind_order(engine: CoordinatorEngine, order: OrderState) -> None:
    profile = engine._flow_for_order(order.spec.order_id)
    engine.unit_contexts[order.spec.order_id] = UnitContext(
        order.spec.order_id,
        profile.picker_id,
        profile.cart.cart_id,
        profile.station.station_id,
        profile.shipper_id,
        order.spec.source_node,
        profile.intake_node,
        profile.output_node,
        profile.port.port_id,
    )
    engine._emit("unit_context_bound", order.spec.order_id)


def ready(engine: CoordinatorEngine, carrier: RunningCarrier, stage: str) -> bool:
    order_id = carrier.job.job_id
    if order_id not in engine.packing_states:
        if stage != "pack":
            raise RuntimeError("CLEAR_WITHOUT_PACKING_ASSIGNMENT")
        reserve_actor(engine, carrier)
        return False
    packing = engine.packing_states[order_id]
    worker = engine.workers[packing.actor_id]
    if worker.order_id != order_id or worker.operation is not None or worker.steps:
        return False
    if worker.node != engine._flow_for_order(order_id).station.node:
        raise RuntimeError("PACKER_NOT_AT_ACTUAL_STATION")
    if packing.phase != ("ready" if stage == "pack" else "packed"):
        raise RuntimeError("PACKING_PHASE_DOES_NOT_MATCH_BELT")
    require_reservation(engine, packing)
    return True


def started(engine: CoordinatorEngine, carrier: RunningCarrier, stage: str) -> None:
    packing = engine.packing_states[carrier.job.job_id]
    worker, order = engine.workers[packing.actor_id], engine.orders[packing.order_id]
    profile = engine._flow_for_order(packing.order_id)
    if stage == "pack":
        _relocate(
            engine,
            packing,
            "package_prepared",
            order.spec.package_id,
            profile.station.bench_owner,
        )
    duration = profile.times.pack if stage == "pack" else profile.times.clear
    packing.phase = stage
    engine._start_operation(worker, HumanStep(stage, profile.station.node, duration))
    order.status = "packing"


def finished(engine: CoordinatorEngine, carrier: RunningCarrier, stage: str) -> None:
    packing = engine.packing_states[carrier.job.job_id]
    worker = engine.workers[packing.actor_id]
    require_reservation(engine, packing)
    engine._finish_operation(worker)
    worker.waiting_since = engine.tick
    if stage == "pack":
        _packed(engine, packing, carrier)
    else:
        _cleared(engine, packing, carrier)


def _packed(engine: CoordinatorEngine, packing: PackingState, carrier: RunningCarrier) -> None:
    order = engine.orders[packing.order_id].spec
    delta = engine.ledger.pack(
        order.order_id + ":pack",
        engine.ledger.revision,
        order.carrier_id,
        order.package_id,
        order.package_placements,
        order_id=order.order_id,
    )
    actual = engine._payload(order.package_id, order.order_id, "sealed_parcel")
    if actual != packing.parcel:
        raise RuntimeError("PACKED_PARCEL_DIFFERS_FROM_RESERVED_PHYSICAL_PAYLOAD")
    packing.phase, packing.packed_tick = "packed", engine.tick
    engine._emit("packed", order.order_id, worker=engine.workers[packing.actor_id], delta=delta)
    carrier.job = replace(
        carrier.job, payload=engine._payload(order.carrier_id, order.order_id, "order_tote")
    )
    engine.belt._emit(carrier, "contents_changed")


def _cleared(engine: CoordinatorEngine, packing: PackingState, carrier: RunningCarrier) -> None:
    order, profile = engine.orders[packing.order_id].spec, engine._flow_for_order(packing.order_id)
    worker = engine.workers[packing.actor_id]
    _relocate(
        engine, packing, "empty_carrier_cleared", order.carrier_id, profile.station.empty_owner
    )
    _relocate(engine, packing, "parcel_loaded", order.package_id, "belt:" + order.order_id)
    engine.belt.replace_payload(carrier, packing.parcel)
    packing.cleared_tick = engine.tick
    for key in packing.engine_resources[1:]:
        del engine.leases[key]
    engine.orders[order.order_id].status = "belt_return"
    if packing.role_intent_id is not None:
        _released(engine, packing, worker)
    else:
        packing.phase = "returning"
        step = travel(profile, worker.spec, profile.station.node, worker.spec.home, "return")
        engine._assign(worker, engine.orders[order.order_id], "packer_return", [step])
    engine._packing_event("packing_cleared", packing, resources=packing.engine_resources[1:])


def task_finished(engine: CoordinatorEngine, worker: HumanState) -> None:
    if worker.steps:
        return
    packing = engine.packing_states[str(worker.order_id)]
    if worker.task == "packer_approach":
        worker.task, packing.phase = "station", "ready"
    else:
        _released(engine, packing, worker)


def _released(engine: CoordinatorEngine, packing: PackingState, worker: HumanState) -> None:
    del engine.leases[packing.engine_resources[0]]
    packing.phase, packing.released_tick = "complete", engine.tick
    worker.stop_waiting(engine.tick)
    worker.order_id, worker.task = None, "idle"
    engine._packing_event("packing_actor_released", packing, resources=packing.engine_resources[:1])


def require_reservation(engine: CoordinatorEngine, packing: PackingState) -> None:
    if any(engine.leases.get(key) != packing.order_id for key in packing.held_resources()):
        raise RuntimeError("PACK_PHYSICAL_RESERVATION_LOST")
    if any(engine.belt.external.get(key) != packing.order_id for key in packing.belt_resources):
        raise RuntimeError("PACK_CLEAR_FOOTPRINT_RESERVATION_LOST")


def _relocate(
    engine: CoordinatorEngine, packing: PackingState, kind: str, identity: str, owner: str
) -> None:
    delta = engine._relocate_material(packing.order_id + ":" + kind, identity, owner)
    engine._emit(kind, packing.order_id, worker=engine.workers[packing.actor_id], delta=delta)
