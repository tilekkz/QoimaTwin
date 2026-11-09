"""Typed compiled vehicle geometry. Unpinned decoding is explicitly geometry-only."""

from collections.abc import Mapping
from types import MappingProxyType

from .runtime_graph_source import _array, _name, _names, _number, _object
from .vehicle_geometry import validate_arc_geometry
from .vehicle_traffic import route_bindings, source_resources, traffic_resources
from .vehicle_types import XYZ, XZ, ArcGeometry, VehicleArc, VehicleGraph, VehicleNode


def vector3(value: object) -> XYZ:
    coordinates = _array(value)
    if len(coordinates) != 3:
        raise ValueError("vehicle XYZ must contain three coordinates")
    return tuple(_number(c, positive=False) for c in coordinates)  # type: ignore[return-value]


def vector2(value: object) -> XZ:
    coordinates = _array(value)
    if len(coordinates) != 2:
        raise ValueError("vehicle XZ must contain two coordinates")
    return (_number(coordinates[0], positive=False), _number(coordinates[1], positive=False))


def _geometry(row: Mapping[str, object]) -> ArcGeometry:
    kind = row.get("kind")
    start, end = (_number(row.get(key), positive=False) for key in ("start_yaw_rad", "end_yaw_rad"))
    if kind == "line":
        return ArcGeometry(
            kind,
            start,
            end,
            vector2(row.get("front_axle_start_xz_m")),
            vector2(row.get("front_axle_end_xz_m")),
        )
    if kind != "rear_steer_arc":
        raise ValueError("unsupported analytic vehicle geometry")
    radius = _number(row.get("icr_vehicle_local_x_m"), positive=False)
    if abs(radius) != _number(row.get("front_axle_radius_m")):
        raise ValueError("curve signed and absolute radii disagree")
    return ArcGeometry(
        kind, start, end, icr_xz=vector2(row.get("icr_world_xz_m")), signed_radius_m=radius
    )


def _node(value: object) -> VehicleNode:
    row = _object(value)
    stopped = row.get("stop_allowed")
    if stopped is not None and type(stopped) is not bool:
        raise ValueError("invalid source stop permission")
    return VehicleNode(
        _name(row.get("node_id")),
        vector3(row.get("world_pos")),
        vector3(row.get("front_axle_world_pos")),
        _number(row.get("yaw_rad"), positive=False),
        stopped,
    )


def _arc(value: object, groups: Mapping[str, tuple[str, ...]]) -> VehicleArc:
    row = _object(value)
    name = _name(row.get("arc_id"))
    direction = row.get("motion_direction")
    if type(direction) is not int or direction not in {-1, 1}:
        raise ValueError("vehicle arc requires explicit signed motion")
    length = _number(row.get("length_m"))
    if length != _number(row.get("cost_m")):
        raise ValueError("vehicle candidate costs must remain metres")
    reference = row.get("source_path_id", row.get("source_edge_id"))
    clearance = row.get("clearance_ref")
    return VehicleArc(
        name,
        _name(row.get("from_node_id")),
        _name(row.get("to_node_id")),
        _geometry(_object(row.get("geometry"))),
        direction,
        length,
        _number(row.get("front_axle_path_length_m")),
        _names(row, "equipment_pair_refs"),
        _names(row, "allowed_geometry_profile_ids"),
        _names(row, "allowed_cargo_archetype_ids"),
        tuple(sorted(_names(row, "source_reservation_group_ids"))),
        groups.get(name, ()),
        _number(row["clear_width_m"]) if "clear_width_m" in row else None,
        _number(row.get("clear_height_m")),
        _name(clearance) if clearance is not None else None,
        _number(row.get("rear_virtual_steer_deg"), positive=False),
        _name(row.get("curvature_transition")),
        _name(reference),
    )


def _validate_graph(graph: VehicleGraph, pair_ids: frozenset[str], source_ids: set[str]) -> None:
    for source_ref, arc_ids in graph.route_bindings.items():
        if any(graph.arcs[arc_id].source_ref != source_ref for arc_id in arc_ids):
            raise ValueError("traffic binding disagrees with the arc's original source reference")
    for arc in graph.arcs.values():
        if arc.source not in graph.nodes or arc.target not in graph.nodes:
            raise ValueError("vehicle arc endpoint is absent")
        if not arc.equipment_pairs or not arc.equipment_pairs <= pair_ids:
            raise ValueError("unknown vehicle equipment pair")
        if not set(arc.source_groups) <= source_ids:
            raise ValueError("unknown original vehicle reservation group")
        if not arc.profiles or (arc.clear_width_m is None and arc.clearance_ref is None):
            raise ValueError("vehicle geometry requires explicit profile and clearance source")
        validate_arc_geometry(
            arc, graph.nodes[arc.source], graph.nodes[arc.target], graph.axle_offset_m
        )


def decode_vehicle_graph(
    layout: Mapping[str, object], traffic: Mapping[str, object], vehicle: Mapping[str, object]
) -> VehicleGraph:
    """Retain directed source restrictions; successful decoding never grants motion."""
    version = _name(layout.get("layout_version"))
    if any(document.get("layout_version") != version for document in (traffic, vehicle)):
        raise ValueError("vehicle source layout versions differ")
    source = _object(layout.get("vehicle_graph"))
    nodes = [_node(value) for value in _array(source.get("nodes"))]
    rows = _array(source.get("arcs"))
    ids = [_name(_object(row).get("arc_id")) for row in rows]
    if len({n.node_id for n in nodes}) != len(nodes) or len(set(ids)) != len(ids):
        raise ValueError("duplicate vehicle node or arc")
    bindings = route_bindings(layout, set(ids))
    resources = source_resources(vehicle)
    source_ids = set(resources)
    groups = traffic_resources(traffic, bindings, resources)
    arcs = [_arc(row, groups) for row in rows]
    graph = VehicleGraph(
        version,
        _number(source.get("front_axle_root_offset_m")),
        MappingProxyType({node.node_id: node for node in nodes}),
        MappingProxyType({arc.arc_id: arc for arc in arcs}),
        MappingProxyType(resources),
        MappingProxyType(bindings),
    )
    _validate_graph(graph, _names(vehicle, "equipment_pair_refs"), source_ids)
    return graph
