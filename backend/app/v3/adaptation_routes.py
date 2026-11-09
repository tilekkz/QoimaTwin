"""Exact route recomputation from compiled directed arc facts (never reported floats)."""

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from app.v3.adaptation_models import ExactRoute, RouteDoc
from app.v3.adaptation_pin import TRANSPORT_GRAPH
from app.v3.runtime_graph import Arc
from app.v3.runtime_graph_source import compiled_graph


@dataclass(frozen=True, slots=True)
class PlanningGraphs:
    """Arc lookup per compiled graph; a read-only view for the planning projection."""

    arcs: Mapping[str, Mapping[str, Arc]]

    @classmethod
    def from_links(cls, links: Mapping[str, Any]) -> "PlanningGraphs":
        return cls(
            {
                graph_id: {arc.arc_id: arc for arc in compiled_graph(links, graph_id).arcs}
                for graph_id in sorted(set(TRANSPORT_GRAPH.values()))
            }
        )


def _carries(arc: Arc, transport: str, archetype: str) -> bool:
    if transport == "manual_cart":
        return "manual_cart" in arc.modes
    return archetype in arc.cargo_classes and bool(arc.profiles)


def exact_route(
    graphs: PlanningGraphs,
    doc: RouteDoc,
    *,
    transport: str,
    archetype: str,
    endpoints: tuple[str, str],
) -> ExactRoute:
    """Validate a declared arc chain for one loaded transport and sum its exact lengths."""
    if TRANSPORT_GRAPH.get(transport) != doc.graph:
        raise ValueError(f"{transport} must use the {TRANSPORT_GRAPH.get(transport)} graph")
    if (doc.from_node_id, doc.to_node_id) != endpoints:
        raise ValueError(f"route endpoints {doc.from_node_id}->{doc.to_node_id} differ")
    arcs = graphs.arcs[doc.graph]
    node, length = doc.from_node_id, Fraction(0)
    for arc_id in doc.arc_ids:
        arc = arcs.get(arc_id)
        if arc is None or arc.source != node:
            raise ValueError(f"{arc_id}: missing or non-contiguous directed arc")
        if not _carries(arc, transport, archetype):
            raise ValueError(f"{arc_id}: arc does not admit {transport} with {archetype}")
        node, length = arc.target, length + arc.length_m
    if node != doc.to_node_id:
        raise ValueError("directed arc chain does not reach the declared end node")
    return ExactRoute(doc.graph, doc.from_node_id, doc.to_node_id, doc.arc_ids, length)


def transport_for(archetype: str, graph: str) -> str:
    """The C11 cost rule: walk legs travel as manual_cart, vehicle legs as forklift_assisted."""
    tags = [tag for tag, graph_id in TRANSPORT_GRAPH.items() if graph_id == graph]
    if len(tags) != 1:
        raise ValueError(f"no unique planning transport for graph {graph!r} ({archetype})")
    return tags[0]
