"""Atomic local pack/clear reservation with a proven helper restoration bound."""

from __future__ import annotations

from fractions import Fraction
from typing import TYPE_CHECKING
from urllib.parse import quote

from app.v3.belt_geometry import footprint, requirements
from app.v3.belt_state import RunningCarrier
from app.v3.conveyor_models import ConveyorPayload
from app.v3.coordinator_observe import assignment
from app.v3.coordinator_packing_models import PackingState
from app.v3.coordinator_validation import role_route
from app.v3.light_flow_plan import travel
from app.v3.light_flow_state import HumanState, HumanStep

if TYPE_CHECKING:
    from app.v3.coordinator_engine import CoordinatorEngine


def reserve_actor(engine: CoordinatorEngine, carrier: RunningCarrier) -> bool:
    order_id = carrier.job.job_id
    station = engine.unit_contexts[order_id].station_id
    helper = engine.station_bindings.get(station)
    candidates = [helper] if helper is not None else [engine._flow_for_order(order_id).packer_id]
    reason = "NO_ACTUAL_PACKER"
    for actor in candidates:
        worker = engine.workers[actor]
        if not engine._worker_eligible(worker, "pack"):
            continue
        plan = prepare(engine, carrier, worker)
        if isinstance(plan, str):
            reason = plan
            continue
        packing, step = plan
        if not engine.belt.reserve(order_id, packing.belt_resources):
            raise RuntimeError("PACK_ATOMIC_RESERVATION_CHANGED_WITHOUT_INTERLEAVING")
        engine.leases.update((key, order_id) for key in packing.engine_resources)
        engine.packing_states[order_id] = packing
        engine.packing_waits.pop(order_id, None)
        engine._packing_event("packing_reserved", packing, resources=packing.engine_resources)
        engine._assign(worker, engine.orders[order_id], "packer_approach", [step])
        return True
    if engine.packing_waits.get(order_id) != reason:
        engine.packing_waits[order_id] = reason
        engine._emit("packing_deferred", order_id)
    return False


def prepare(
    engine: CoordinatorEngine,
    carrier: RunningCarrier,
    worker: HumanState,
) -> tuple[PackingState, HumanStep] | str:
    profile = engine._flow_for_order(carrier.job.job_id)
    if worker.node is None:
        return "PACKER_HAS_NO_ACTUAL_NODE"
    step = travel(profile, worker.spec, worker.node, profile.station.node, "travel_empty")
    intent = assignment(engine, worker.spec.actor_id)
    if intent is not None:
        duration, _ = role_route(
            engine.coordinator,
            worker.spec.actor_id,
            profile.station.node,
            intent.intent.restore_node,
        )
        local_end = engine.tick + step.duration + profile.times.pack + profile.times.clear
        if (
            local_end > intent.intent.return_tick
            or intent.intent.return_tick + duration > intent.intent.restore_by_tick
        ):
            return "HELPER_RESTORATION_BOUND"
    payload = predicted_parcel(engine, carrier.job.job_id)
    empty = engine.ledger.contents(engine.orders[carrier.job.job_id].spec.carrier_id).container
    if max(payload.gross_mass_kg, empty.recipe.tare_kg) > worker.spec.max_gross_kg:
        return "PACKER_GROSS_CAPACITY"
    resources = local_resources(engine, carrier, payload)
    owned = ownership_resources(engine, carrier.job.job_id, worker.spec.actor_id)
    if not _capacity(engine, profile.station.bench_owner, "bench"):
        return "PACK_BENCH_OCCUPIED"
    if not _capacity(engine, profile.station.empty_owner, "empty"):
        return "EMPTY_CARRIER_RACK_FULL"
    if not _free(engine, carrier.job.job_id, resources, owned):
        return "PACK_CLEAR_RESERVATION_BLOCKED"
    return PackingState(
        carrier.job.job_id,
        worker.spec.actor_id,
        profile.station.station_id,
        intent.intent.intent_id if intent else None,
        engine.tick,
        payload,
        resources,
        owned,
        worker.node,
    ), step


def predicted_parcel(engine: CoordinatorEngine, order_id: str) -> ConveyorPayload:
    order = engine.orders[order_id].spec
    carrier, package = (
        engine.ledger.contents(order.carrier_id),
        engine.ledger.contents(order.package_id),
    )
    if (
        package.units
        or package.container.owner_id != engine._flow_for_order(order_id).package_pool_owner
    ):
        raise RuntimeError("PACK_PACKAGE_NOT_IN_DECLARED_EMPTY_POOL")
    if {u.token.unit_id for u in carrier.units} != {p.unit_id for p in order.package_placements}:
        raise RuntimeError("PACK_ACTUAL_CONTENTS_DIFFER_FROM_ORDER")
    gross = package.container.recipe.tare_kg + sum(
        (unit.token.recipe.gross_mass_kg for unit in carrier.units), Fraction(0)
    )
    return ConveyorPayload(
        order.package_id,
        "sealed_parcel",
        package.container.recipe.outer,
        gross,
        "upright_xyz",
        order_id,
        package.container.recipe.provenance,
    )


def local_resources(
    engine: CoordinatorEngine,
    state: RunningCarrier,
    payload: ConveyorPayload,
) -> frozenset[str]:
    engine.belt._replacement_steps(state, payload)
    if state.pose is None:
        raise RuntimeError("PACK_REPLACEMENT_HAS_NO_ACTUAL_POSE")
    target = requirements(engine.belt.source, footprint(engine.belt.source, payload, state.pose))
    return target | state.steps[state.index].resources | state.steps[state.index + 1].resources


def ownership_resources(engine: CoordinatorEngine, order_id: str, actor: str) -> tuple[str, ...]:
    station = engine._flow_for_order(order_id).station
    package = engine.orders[order_id].spec.package_id
    return (
        "pack:worker:" + actor,
        "pack:bench:" + quote(station.bench_owner, safe=""),
        "pack:empty:" + quote(station.empty_owner, safe="") + ":" + quote(order_id, safe=""),
        "pack:material:" + quote(package, safe=""),
    )


def _capacity(engine: CoordinatorEngine, owner: str, kind: str) -> bool:
    maximum = next(o.capacity for o in engine.profile.owners if o.owner_id == owner)
    occupied = sum(c.owner_id == owner for c in engine.ledger.snapshot().containers)
    prefix = "pack:" + kind + ":" + quote(owner, safe="")
    reserved = sum(key == prefix or key.startswith(prefix + ":") for key in engine.leases)
    return occupied + reserved < maximum


def _free(
    engine: CoordinatorEngine, order: str, belt: frozenset[str], owned: tuple[str, ...]
) -> bool:
    return all(key not in engine.leases for key in owned) and all(
        engine.belt.leases.get(key, order) == order
        and engine.belt.external.get(key, order) == order
        for key in belt
    )
