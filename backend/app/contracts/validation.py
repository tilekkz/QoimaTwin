"""Semantic checks that JSON Schema cannot express (references, geometry, counts).

Every function returns a list of human-readable issues; an empty list means the input passed.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable
from fractions import Fraction
from typing import TYPE_CHECKING

from app.contracts.base import Vec3, exact, exact_vec
from app.contracts.layout import Graph, Layout, Rack, Segment

if TYPE_CHECKING:
    from app.contracts.loader import ContractBundle


def axis_distance(a: Vec3, b: Vec3) -> Fraction | None:
    """Exact length of an axis-aligned segment in the X/Z plane; None if it is diagonal."""
    pa, pb = exact_vec(a), exact_vec(b)
    dx, dy, dz = (abs(pb[i] - pa[i]) for i in range(3))
    if dy != 0 or (dx != 0 and dz != 0):
        return None
    return dx + dz


def _duplicates(ids: Iterable[str]) -> list[str]:
    return sorted(key for key, count in Counter(ids).items() if count > 1)


def _check_graph(name: str, graph: Graph) -> list[str]:
    issues = [f"{name}: duplicate node id {d}" for d in _duplicates(n.node_id for n in graph.nodes)]
    positions = {n.node_id: n.pos for n in graph.nodes}
    for edge in graph.edges:
        if edge.a not in positions or edge.b not in positions:
            issues.append(f"{name}: edge {edge.a}-{edge.b} references an unknown node")
            continue
        if edge.a == edge.b:
            issues.append(f"{name}: self-loop edge at {edge.a}")
            continue
        length = axis_distance(positions[edge.a], positions[edge.b])
        if length is None:
            issues.append(f"{name}: edge {edge.a}-{edge.b} is not axis-aligned")
        elif length != exact(edge.length_m):
            issues.append(
                f"{name}: edge length {edge.a}-{edge.b} is {edge.length_m}, "
                f"geometry gives {float(length)}"
            )
    pairs = Counter(tuple(sorted((e.a, e.b))) for e in graph.edges)
    issues.extend(f"{name}: duplicate edge {a}-{b}" for (a, b), c in sorted(pairs.items()) if c > 1)
    return issues


PlanePoint = tuple[int, int]
RackFootprint = tuple[str, int, int, int, int]


def _plane_scale(values: Iterable[Fraction]) -> int:
    """Smallest integer that turns every given exact coordinate into an integer."""
    scale = 1
    for value in values:
        scale = math.lcm(scale, value.denominator)
    return scale


def _footprint(rack: Rack, scale: int) -> RackFootprint:
    root, size = exact_vec(rack.root), exact_vec(rack.size)
    return (
        rack.rack_id,
        int((root[0] - size[0] / 2) * scale),
        int((root[0] + size[0] / 2) * scale),
        int((root[2] - size[2] / 2) * scale),
        int((root[2] + size[2] / 2) * scale),
    )


def _crosses_rack(p: PlanePoint, q: PlanePoint, footprint: RackFootprint) -> bool:
    """True if an axis-aligned X/Z segment enters the open interior of a rack footprint."""
    _, xmin, xmax, zmin, zmax = footprint
    if p[0] == q[0]:
        overlap = max(min(p[1], q[1]), zmin) < min(max(p[1], q[1]), zmax)
        return xmin < p[0] < xmax and overlap
    overlap = max(min(p[0], q[0]), xmin) < min(max(p[0], q[0]), xmax)
    return zmin < p[1] < zmax and overlap


def _check_rack_crossings(layout: Layout) -> list[str]:
    graph = layout.picker_graph
    raw = {n.node_id: n.pos for n in graph.nodes}
    exact_nodes = {node_id: exact_vec(pos) for node_id, pos in raw.items()}
    rack_values = [v for r in layout.racks for v in (*exact_vec(r.root), *exact_vec(r.size))]
    node_values = [v for pos in exact_nodes.values() for v in pos]
    scale = _plane_scale([*node_values, *rack_values]) * 2  # half sizes stay integral
    plane = {n: (int(p[0] * scale), int(p[2] * scale)) for n, p in exact_nodes.items()}
    footprints = [_footprint(rack, scale) for rack in layout.racks]
    issues: list[str] = []
    for edge in graph.edges:
        if edge.a not in plane or edge.b not in plane:
            continue
        if axis_distance(raw[edge.a], raw[edge.b]) is None:
            continue
        issues += [
            f"picker edge {edge.a}-{edge.b} crosses rack {fp[0]}"
            for fp in footprints
            if _crosses_rack(plane[edge.a], plane[edge.b], fp)
        ]
    return issues


def _check_racks_and_slots(layout: Layout) -> list[str]:
    nodes = {n.node_id for n in layout.picker_graph.nodes}
    racks = {r.rack_id: r for r in layout.racks}
    issues = [f"duplicate rack id {d}" for d in _duplicates(r.rack_id for r in layout.racks)]
    issues += [f"duplicate slot id {d}" for d in _duplicates(s.slot_id for s in layout.slots)]
    issues += _check_rack_crossings(layout)
    for slot in layout.slots:
        if slot.rack_id not in racks:
            issues.append(f"slot {slot.slot_id} references unknown rack {slot.rack_id}")
        if slot.kind == "pickface":
            if slot.level != 1 or slot.service_node_id not in nodes:
                issues.append(
                    f"pickface slot {slot.slot_id} needs level 1 and a known service node"
                )
        elif slot.service_node_id is not None or slot.level == 1:
            issues.append(f"reserve slot {slot.slot_id} must be level 2/3 without walk access")
    return issues


def _check_segment(segment: Segment) -> list[str]:
    length = axis_distance(segment.start, segment.end)
    expected = exact(segment.cell_length_m) * segment.cell_count
    if length is None:
        return [f"segment {segment.segment_id} is not axis-aligned"]
    if not (length == exact(segment.length_m) == expected):
        return [f"segment {segment.segment_id}: length {length} != cells {expected}"]
    return []


def port_offset(segment: Segment, port: Vec3) -> Fraction | None:
    """Exact distance from the segment start to a port that lies on the segment, else None."""
    to_port = axis_distance(segment.start, port)
    from_port = axis_distance(port, segment.end)
    if to_port is None or from_port is None or to_port + from_port != exact(segment.length_m):
        return None
    return to_port


def _check_conveyor(layout: Layout) -> list[str]:
    conveyor = layout.conveyor
    segments = {s.segment_id: s for s in conveyor.segments}
    issues = [
        f"duplicate segment id {d}" for d in _duplicates(s.segment_id for s in conveyor.segments)
    ]
    for segment in conveyor.segments:
        issues += _check_segment(segment)
    total = sum(s.cell_count for s in conveyor.segments)
    if total != conveyor.total_cell_count:
        issues.append(f"conveyor has {total} cells, declared {conveyor.total_cell_count}")
    cell = exact(conveyor.cell_length_m)
    for link in conveyor.connections:
        source, target = segments.get(link.from_segment_id), segments.get(link.to_segment_id)
        if source is None or target is None:
            issues.append(
                f"connection {link.from_segment_id}->{link.to_segment_id} has unknown segment"
            )
            continue
        name = f"connection {link.from_segment_id}->{link.to_segment_id}"
        src_off, dst_off = port_offset(source, link.at), port_offset(target, link.at)
        if src_off is None or dst_off is None:
            issues.append(f"{name} port is off-segment")
            continue
        on_boundary = src_off % cell == 0 and dst_off % cell == 0
        if not on_boundary or src_off == 0 or dst_off == exact(target.length_m):
            issues.append(f"{name} port is not a valid cell boundary")
    if conveyor.terminal.segment_id not in segments:
        issues.append(f"terminal segment {conveyor.terminal.segment_id} is unknown")
    for station in layout.pack_stations:
        for seg_id in (station.input_segment_id, station.output_segment_id):
            if seg_id not in segments:
                issues.append(f"pack station {station.pack_id} references unknown segment {seg_id}")
    for induction in layout.inductions:
        if induction.feed_segment_id not in segments:
            issues.append(f"induction {induction.induction_id} references unknown feed segment")
    return issues


def _check_counts(layout: Layout) -> list[str]:
    counts = layout.counts
    actual = {
        "racks": len(layout.racks),
        "slots": len(layout.slots),
        "pickfaces": sum(1 for s in layout.slots if s.kind == "pickface"),
        "reserve_slots": sum(1 for s in layout.slots if s.kind == "reserve"),
        "picker_nodes": len(layout.picker_graph.nodes),
        "picker_edges": len(layout.picker_graph.edges),
    }
    return [
        f"count {key}: declared {getattr(counts, key)}, actual {value}"
        for key, value in actual.items()
        if getattr(counts, key) != value
    ]


def validate_layout(layout: Layout) -> list[str]:
    issues = _check_graph("picker_graph", layout.picker_graph)
    issues += _check_graph("forklift inbound", layout.forklift_graphs.inbound)
    issues += _check_graph("forklift outbound", layout.forklift_graphs.outbound)
    issues += _check_racks_and_slots(layout)
    issues += _check_conveyor(layout)
    issues += _check_counts(layout)
    node_ids = {n.node_id for n in layout.picker_graph.nodes}
    for node in (layout.relocation_home_node_id, layout.relocation_buffer_node_id):
        if node not in node_ids:
            issues.append(f"relocation node {node} is unknown")
    for induction in layout.inductions:
        if induction.home_node_id not in node_ids:
            issues.append(f"induction {induction.induction_id} home node is unknown")
    return issues


def validate_bundle(bundle: ContractBundle) -> list[str]:
    layout, config, registry = bundle.layout, bundle.config, bundle.actors
    issues = validate_layout(layout)
    for name, version in (("config", config.layout_version), ("actors", registry.layout_version)):
        if version != layout.layout_version:
            issues.append(f"{name} layout_version {version} != {layout.layout_version}")
    loop_cells = exact(layout.conveyor.loop_length_m) / exact(layout.conveyor.cell_length_m)
    if config.totes_total >= loop_cells:
        issues.append(
            f"tote pool {config.totes_total} must stay below {loop_cells} loop cells (ADR 0004)"
        )
    issues += [f"duplicate actor id {d}" for d in _duplicates(a.actor_id for a in registry.actors)]
    staffing = config.staffing.model_dump()
    for role, count in staffing.items():
        actual = sum(1 for a in registry.actors if a.role == role)
        if actual != count:
            issues.append(f"staffing {role}: config {count}, actors {actual}")
    issues += _check_actor_links(bundle)
    return issues


def _check_actor_links(bundle: ContractBundle) -> list[str]:
    layout, registry = bundle.layout, bundle.actors
    issues: list[str] = []
    homes = {i.home_node_id for i in layout.inductions}
    packs = {p.pack_id for p in layout.pack_stations}
    vehicles = {v.vehicle_id: v for v in registry.vehicles}
    forklift_nodes = {
        "inbound": {n.node_id for n in layout.forklift_graphs.inbound.nodes},
        "outbound": {n.node_id for n in layout.forklift_graphs.outbound.nodes},
    }
    for actor in registry.actors:
        if actor.role == "picker" and actor.home_node_id not in homes:
            issues.append(f"picker {actor.actor_id} home is not an induction")
        if actor.role == "packer" and actor.pack_id not in packs:
            issues.append(f"packer {actor.actor_id} pack station is unknown")
        if actor.role == "forklift_driver":
            vehicle = vehicles.get(actor.vehicle_id or "")
            if vehicle is None or vehicle.driver_actor_id != actor.actor_id:
                issues.append(f"driver {actor.actor_id} is not linked to its vehicle")
            elif actor.home_node_id not in forklift_nodes[vehicle.graph_id]:
                issues.append(
                    f"driver {actor.actor_id} home is not on the {vehicle.graph_id} graph"
                )
    pickers_per_home = Counter(a.home_node_id for a in registry.actors if a.role == "picker")
    issues += [
        f"home {h} has {c} pickers, expected 4"
        for h, c in sorted(pickers_per_home.items())
        if c != 4
    ]
    return issues
