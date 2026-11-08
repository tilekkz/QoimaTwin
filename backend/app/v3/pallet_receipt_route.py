"""Source-permitted directed candidate, retaining actual arc poses and stage resources."""

import heapq
from fractions import Fraction
from itertools import pairwise

from app.v3.pallet_receipt_types import PalletReceiptError, PalletRouteCandidate, RouteStop
from app.v3.vehicle_source import VehicleAdapter
from app.v3.vehicle_types import VehicleArc


def candidate_route(adapter: VehicleAdapter, start: str, target: str) -> PalletRouteCandidate:
    if start not in adapter.graph.nodes or target not in adapter.graph.nodes:
        raise PalletReceiptError("UNKNOWN_VEHICLE_POSE", "source service/prehandle node absent")
    adjacency: dict[str, list[VehicleArc]] = {}
    for arc in adapter.graph.arcs.values():
        if adapter.declared_loaded_arc(arc.arc_id, "PALLET_LOAD", "INBOUND_FORKLIFT_PAIR"):
            adjacency.setdefault(arc.source, []).append(arc)
    path = _shortest(adjacency, start, target)
    arcs = tuple(adapter.graph.arcs[key] for key in path)
    nodes = (start, *(arc.target for arc in arcs))
    stops = tuple(
        _stop(adapter, a, b)
        for a, b in pairwise(arcs)
        if (a.motion_direction, a.rear_steer_deg) != (b.motion_direction, b.rear_steer_deg)
    )
    names = {key for arc in arcs for key in (*arc.source_groups, *arc.traffic_groups)}
    resources = tuple((key, adapter.graph.resources[key].capacity) for key in sorted(names))
    return PalletRouteCandidate(
        nodes, arcs, sum((a.root_length_m for a in arcs), Fraction(0)), stops, resources
    )


def _shortest(adjacency: dict[str, list[VehicleArc]], start: str, target: str) -> tuple[str, ...]:
    pending: list[tuple[Fraction, tuple[str, ...], str]] = [(Fraction(0), (), start)]
    best: dict[str, tuple[Fraction, tuple[str, ...]]] = {start: (Fraction(0), ())}
    while pending:
        distance, path, node = heapq.heappop(pending)
        if best[node] != (distance, path):
            continue
        if node == target:
            return path
        for arc in sorted(adjacency.get(node, []), key=lambda a: a.arc_id):
            if arc.root_length_m <= 0:
                raise PalletReceiptError("NONPOSITIVE_VEHICLE_ARC", arc.arc_id)
            candidate = distance + arc.root_length_m, (*path, arc.arc_id)
            previous = best.get(arc.target)
            if previous is None or candidate < previous:
                best[arc.target] = candidate
                heapq.heappush(pending, (*candidate, arc.target))
    raise PalletReceiptError(
        "NO_PERMITTED_LOADED_ROUTE", "C08 cargo/pair restrictions disconnect endpoints"
    )


def _stop(adapter: VehicleAdapter, left: VehicleArc, right: VehicleArc) -> RouteStop:
    reasons = []
    if left.motion_direction != right.motion_direction:
        reasons.append("motion_direction_change")
    if left.rear_steer_deg != right.rear_steer_deg:
        reasons.append("curvature_steering_change")
    return RouteStop(
        left.target,
        left.arc_id,
        right.arc_id,
        tuple(reasons),
        adapter.graph.nodes[left.target].stop_allowed,
    )
