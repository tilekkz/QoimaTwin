"""Explicit paid operations for whole-HU hand carrying; no inferred local connector."""

from app.v3.execution_state import Step
from app.v3.execution_types import ActorSpec, ExecutionProfile, PlaceSpec, PortSpec, TimedJob
from app.v3.runtime_graph import DirectedGraph, RouteRequirements
from app.v3.runtime_time import travel_ticks


def _move(graph: DirectedGraph, actor: ActorSpec, source: str, target: str, stage: str) -> Step:
    route = graph.shortest_path(source, target, RouteRequirements(mode="pedestrian"))
    if route is None:
        raise ValueError("no directed pedestrian candidate")
    return Step(stage, travel_ticks(route.length_m, actor.speed_m_s), target, route=route)


def _inbound(
    profile: ExecutionProfile,
    job: TimedJob,
    port: PortSpec,
    actor: ActorSpec,
    buffer: PlaceSpec,
    slot: PlaceSpec,
    graph: DirectedGraph,
) -> list[Step]:
    hu = next(h for h in profile.handling_units if h.hu_id == job.hu_id)
    return [
        _move(graph, actor, actor.home_node_id, port.service_node_id, "approach_port"),
        Step(
            "intake_service",
            dict(port.service_ticks)[hu.archetype],
            port.service_node_id,
            "intake_complete",
        ),
        _move(graph, actor, port.service_node_id, buffer.node_id, "carry_to_buffer"),
        Step("place_buffer", profile.handling.place_ticks, buffer.node_id, "place_buffer"),
        Step("pickup_buffer", profile.handling.pickup_ticks, buffer.node_id, "pickup_buffer"),
        _move(graph, actor, buffer.node_id, slot.node_id, "carry_to_slot"),
        Step("place_stock", profile.handling.place_ticks, slot.node_id, "place_stock"),
        _move(graph, actor, slot.node_id, actor.home_node_id, "return_home"),
    ]


def _outbound(
    profile: ExecutionProfile,
    job: TimedJob,
    port: PortSpec,
    actor: ActorSpec,
    buffer: PlaceSpec,
    slot: PlaceSpec,
    graph: DirectedGraph,
) -> list[Step]:
    hu = next(h for h in profile.handling_units if h.hu_id == job.hu_id)
    return [
        _move(graph, actor, actor.home_node_id, slot.node_id, "approach_stock"),
        Step("pickup_stock", profile.handling.pickup_ticks, slot.node_id, "pickup_stock"),
        _move(graph, actor, slot.node_id, buffer.node_id, "carry_to_buffer"),
        Step("place_buffer", profile.handling.place_ticks, buffer.node_id, "place_buffer"),
        Step("outbound_gate", 0, buffer.node_id, "outbound_gate"),
        Step("pickup_buffer", profile.handling.pickup_ticks, buffer.node_id, "pickup_buffer"),
        _move(graph, actor, buffer.node_id, port.service_node_id, "carry_to_port"),
        Step(
            "shipping_service", dict(port.service_ticks)[hu.archetype], port.service_node_id, "ship"
        ),
        _move(graph, actor, port.service_node_id, actor.home_node_id, "return_home"),
    ]


def job_plan(
    profile: ExecutionProfile,
    job: TimedJob,
    actor: ActorSpec,
    buffer: PlaceSpec,
    graph: DirectedGraph,
) -> list[Step] | None:
    port = next(p for p in profile.ports if p.port_id == job.port_id)
    slot = next(s for s in profile.slots if s.place_id == job.slot_id)
    build = _inbound if job.direction == "inbound" else _outbound
    try:
        return build(profile, job, port, actor, buffer, slot, graph)
    except ValueError:
        return None


def service_window(port: PortSpec, now: int, steps: list[Step], horizon: int) -> bool:
    elapsed = 0
    for step in steps:
        if step.stage in {"intake_service", "shipping_service"}:
            start, finish = now + elapsed, now + elapsed + step.ticks
            return any(
                a <= start < min(b, horizon) and finish <= min(b, horizon) for a, b in port.windows
            )
        elapsed += step.ticks
    raise RuntimeError("manual operation sequence has no service")


def next_service_wake(port: PortSpec, now: int, steps: list[Step], horizon: int) -> int | None:
    """Wake early enough to pay the exact pre-service prefix before a future opening."""
    elapsed = 0
    for step in steps:
        if step.stage in {"intake_service", "shipping_service"}:
            candidates = [
                start - elapsed
                for start, end in port.windows
                if start - elapsed > now and start + step.ticks <= min(end, horizon)
            ]
            return min(candidates, default=None)
        elapsed += step.ticks
    raise RuntimeError("manual operation sequence has no service")
