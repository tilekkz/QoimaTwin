"""Exact complete uncontended work; arbitrary hand graphs provide no source authority."""

from fractions import Fraction as F

from app.v3.outbound_placement_models import PlacementCost, PlacementCostFacts, PlacementOperation
from app.v3.outbound_placement_validation import positive_tick, validate_actor
from app.v3.pallet_outbound_pickup_identity import require
from app.v3.runtime_graph import DirectedGraph, RouteRequirements
from app.v3.runtime_time import TICKS_PER_SECOND, operation_ticks
from app.v3.stock_validation import exact, vector


def _travel(
    graph: DirectedGraph, f: PlacementCostFacts, start: str, end: str, kind: str, loaded: bool
) -> PlacementOperation:
    width = (
        max(f.min_width_m, f.dimensions[0] + 2 * f.path_clearance_m) if loaded else f.min_width_m
    )
    height = max(f.min_height_m, f.dimensions[1] + f.path_clearance_m) if loaded else f.min_height_m
    route = graph.shortest_path(
        start,
        end,
        RouteRequirements(
            mode="pedestrian",
            cargo=f.archetype if loaded else None,
            min_clear_width_m=width,
            min_clear_height_m=height,
        ),
    )
    require(route is not None, "MISSING_DIRECTED_ROUTE")
    assert route is not None
    seconds = route.length_m / f.actor.speed_m_s
    return PlacementOperation(kind, seconds, operation_ticks(seconds), route)


def _handle(kind: str, ticks: int) -> PlacementOperation:
    positive_tick(ticks)
    return PlacementOperation(kind, F(ticks, TICKS_PER_SECOND), ticks, None)


def _relocation(graph: DirectedGraph, f: PlacementCostFacts) -> tuple[PlacementOperation, ...]:
    return (
        _travel(graph, f, f.actor.home_node_id, f.source_node, "relocation_approach", False),
        _handle("relocation_take", f.take_ticks),
        _travel(graph, f, f.source_node, f.target_node, "relocation_carry", True),
        _handle("relocation_place", f.place_ticks),
        _travel(graph, f, f.target_node, f.actor.home_node_id, "relocation_return", False),
    )


def _customer(
    graph: DirectedGraph, f: PlacementCostFacts, source: str
) -> tuple[PlacementOperation, ...]:
    return (
        _travel(graph, f, f.actor.home_node_id, source, "whole_approach", False),
        _handle("whole_pick_slot", f.pickup_ticks),
        _travel(graph, f, source, f.buffer_node, "whole_carry_buffer", True),
        _handle("whole_place_buffer", f.customer_place_ticks),
        _handle("whole_pick_buffer", f.pickup_ticks),
        _travel(graph, f, f.buffer_node, f.port_node, "whole_carry_port", True),
        _handle("whole_service", f.service_ticks),
        _travel(graph, f, f.port_node, f.actor.home_node_id, "whole_return", False),
    )


def price_candidate(graph: DirectedGraph, facts: PlacementCostFacts) -> PlacementCost:
    """Pure arithmetic helper only; public decisions construct graphs from pinned bytes."""
    require(type(facts) is PlacementCostFacts, "Exact PlacementCostFacts required")
    require(all(arc.cost_m == arc.length_m for arc in graph.arcs), "V3_DISTANCE_COST_REQUIRED")
    validate_actor(facts.actor)
    vector(facts.dimensions)
    exact(facts.min_width_m, positive=True)
    exact(facts.min_height_m, positive=True)
    exact(facts.path_clearance_m)
    relocation = _relocation(graph, facts)
    baseline, adapted = (
        _customer(graph, facts, node) for node in (facts.source_node, facts.target_node)
    )
    transfer, before, after = (
        sum(op.ticks for op in rows) for rows in (relocation, baseline, adapted)
    )
    return PlacementCost(
        relocation,
        baseline,
        adapted,
        transfer,
        before,
        after,
        before - after,
        before - after - transfer,
    )
