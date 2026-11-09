"""Strict structural decoding of source conveyor records to immutable values."""

from collections.abc import Callable, Mapping
from fractions import Fraction
from types import MappingProxyType
from typing import Any

from app.v3.conveyor_models import (
    ConveyorArc,
    ConveyorCell,
    ConveyorEdge,
    ConveyorNode,
    ConveyorResource,
    ConveyorStation,
    Point,
)
from app.v3.runtime_time import nonnegative_fraction


def text(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Source requires a nonempty string")
    return value


def positive(value: Any) -> Fraction:
    number = nonnegative_fraction(value)
    if number == 0:
        raise ValueError("Source requires positive quantity")
    return number


def count(value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("Source requires positive integer capacity")
    return value


def point(value: Any) -> Point:
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError("Source requires xyz point")
    return (
        nonnegative_fraction(value[0]),
        nonnegative_fraction(value[1]),
        nonnegative_fraction(value[2]),
    )


def indexed[T](rows: Any, key: str, decoder: Callable[[dict[str, Any]], T]) -> Mapping[str, T]:
    if not isinstance(rows, list) or not rows:
        raise ValueError("Source requires nonempty records")
    result: dict[str, T] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Source record must be an object")
        identity = text(row[key])
        if identity in result:
            raise ValueError("Duplicate source identity")
        result[identity] = decoder(row)
    return MappingProxyType(result)


def node(row: dict[str, Any]) -> ConveyorNode:
    return ConveyorNode(text(row["node_id"]), point(row["world_pos"]), text(row["node_type"]))


def edge(row: dict[str, Any]) -> ConveyorEdge:
    kind = text(row["path_kind"])
    if kind not in ("straight", "arc"):
        raise ValueError("Unknown conveyor edge path kind")
    dwell = nonnegative_fraction(row.get("requires_turn_dwell_s", 0))
    turn = text(row["turn_at_node_id"]) if dwell else None
    if dwell and row.get("turn_timing") not in ("before_edge", "after_edge"):
        raise ValueError("Unsupported turn timing")
    if not dwell and ("turn_at_node_id" in row or "turn_timing" in row):
        raise ValueError("Turn metadata without positive dwell")
    arc = None
    if kind == "arc":
        arc = ConveyorArc(
            point(row["centre"]),
            positive(row["radius_m"]),
            signed(row["theta_start_rad"]),
            signed(row["theta_end_rad"]),
        )
        if arc.theta_start_rad <= arc.theta_end_rad:
            raise ValueError("Unsupported arc direction")
    return ConveyorEdge(
        text(row["edge_id"]),
        text(row["from_node_id"]),
        text(row["to_node_id"]),
        text(row["resource_id"]),
        positive(row["length_m"]),
        kind,
        dwell,
        turn,
        text(row["turn_timing"]) if dwell else None,
        arc,
    )


def cell(row: dict[str, Any]) -> ConveyorCell:
    theta = row.get("theta_range")
    angles = None
    if theta is not None:
        if not isinstance(theta, list) or len(theta) != 2:
            raise ValueError("Arc cell requires angular interval")
        angles = (signed(theta[0]), signed(theta[1]))
        if angles[0] <= angles[1] or "position" in row or "length_m" in row:
            raise ValueError("Unsupported arc cell geometry")
    return ConveyorCell(
        text(row["cell_id"]),
        point(row["position"]) if angles is None else None,
        positive(row["length_m"]) if angles is None else None,
        text(row["resource_id"]),
        count(row["max_handling_units"]),
        angles,
    )


def signed(value: Any) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Source requires finite signed numeric angle")
    return Fraction(str(value))


def resource(row: dict[str, Any]) -> ConveyorResource:
    kind = row.get("resource_type", "exclusive")
    if kind not in ("exclusive", "cell_collection"):
        raise ValueError("Unknown resource type")
    cells = row["member_cell_ids"]
    if not isinstance(cells, list) or not cells or len(set(cells)) != len(cells):
        raise ValueError("Resource requires unique member cells")
    if kind == "cell_collection" and count(row.get("per_cell_capacity")) != 1:
        raise ValueError("Unsupported per-cell capacity")
    return ConveyorResource(
        text(row["resource_id"]),
        count(row["capacity"]),
        tuple(text(c) for c in cells),
        kind != "cell_collection",
    )


def station(row: dict[str, Any]) -> ConveyorStation:
    return ConveyorStation(
        text(row["pack_id"]), text(row["work_node_id"]), text(row["spur_resource_id"])
    )
