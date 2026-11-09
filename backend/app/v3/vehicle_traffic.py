"""Resolve original L11 route refs onto compiled directed arcs, without grants."""

from collections.abc import Mapping

from .runtime_graph_source import _array, _name, _names, _object
from .vehicle_types import VehicleResource


def route_bindings(layout: Mapping[str, object], arc_ids: set[str]) -> dict[str, tuple[str, ...]]:
    result: dict[str, tuple[str, ...]] = {}
    covered: set[str] = set()
    for value in _array(layout.get("traffic_route_bindings")):
        row = _object(value)
        if row.get("compiled_graph") != "vehicle":
            continue
        reference = _name(row.get("route_ref"))
        arcs = tuple(sorted(_names(row, "compiled_arc_ids")))
        if reference in result or not arcs or not set(arcs) <= arc_ids:
            raise ValueError("duplicate or unresolved vehicle traffic route binding")
        result[reference] = arcs
        covered.update(arcs)
    if covered != arc_ids:
        raise ValueError("every vehicle arc requires a traffic route binding")
    return result


def source_resources(vehicle: Mapping[str, object]) -> dict[str, VehicleResource]:
    result: dict[str, VehicleResource] = {}
    for value in _array(vehicle.get("reservation_groups")):
        row = _object(value)
        name = _name(row.get("reservation_group_id"))
        if name in result or type(row.get("capacity_vehicles")) is not int:
            raise ValueError("duplicate or invalid vehicle reservation resource")
        if row["capacity_vehicles"] != 1:
            raise ValueError("source vehicle reservation groups have capacity one")
        result[name] = VehicleResource(name, 1)
    return result


def traffic_resources(
    traffic: Mapping[str, object],
    bindings: Mapping[str, tuple[str, ...]],
    resources: dict[str, VehicleResource],
) -> dict[str, tuple[str, ...]]:
    by_arc: dict[str, set[str]] = {}
    mixed = _object(traffic.get("mixed_traffic"))
    for value in _array(mixed.get("resources")):
        row = _object(value)
        name = _name(row.get("resource_id"))
        if name in resources or type(row.get("capacity_occupants")) is not int:
            raise ValueError("duplicate or invalid mixed traffic resource")
        if row["capacity_occupants"] != 1:
            raise ValueError("mixed traffic resources have capacity one")
        references = tuple(sorted(_names(row, "vehicle_route_refs")))
        if not set(references) <= bindings.keys():
            raise ValueError("unresolved original vehicle traffic reference")
        resources[name] = VehicleResource(
            name, 1, references, tuple(sorted(_names(row, "human_route_refs")))
        )
        for reference in references:
            for arc_id in bindings[reference]:
                by_arc.setdefault(arc_id, set()).add(name)
    return {arc_id: tuple(sorted(groups)) for arc_id, groups in by_arc.items()}
