"""Read compiled V3 graph structure; collision/admission proof belongs to separate validators."""

from collections.abc import Mapping
from fractions import Fraction
from typing import cast

from app.v3.runtime_graph import Arc, DirectedGraph
from app.v3.runtime_time import nonnegative_fraction

LAYOUT_VERSION = "qoima-144x72-v3-proposal"


def _object(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise ValueError("compiled graph requires objects with string keys")
    return cast(Mapping[str, object], value)


def _array(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ValueError("compiled graph requires arrays")
    return value


def _name(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("compiled graph requires nonempty identifiers")
    return value


def _number(value: object, *, positive: bool = True) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("compiled graph requires finite JSON numbers")
    if not positive and value < 0:
        return -nonnegative_fraction(-value)
    result = nonnegative_fraction(value)
    if positive and result <= 0:
        raise ValueError("compiled graph metrics must be positive")
    return result


def _names(row: Mapping[str, object], key: str) -> frozenset[str]:
    values = [_name(value) for value in _array(row.get(key, []))]
    if len(values) != len(set(values)):
        raise ValueError("duplicate compiled graph permission")
    return frozenset(values)


def _width(row: Mapping[str, object]) -> Fraction | None:
    found = [_number(row[key]) for key in ("width_m", "clear_width_m") if key in row]
    if len(set(found)) > 1:
        raise ValueError("conflicting declared clear widths")
    return found[0] if found else None


def _cargo(row: Mapping[str, object]) -> frozenset[str]:
    classes = _names(row, "allowed_cargo_archetype_ids")
    if "cargo_transport_supported" in row:
        supported = row["cargo_transport_supported"]
        if type(supported) is not bool or (supported is False and classes):
            raise ValueError("cargo permissions conflict with declared support")
    return classes


def _node(value: object) -> str:
    row = _object(value)
    position = _array(row.get("world_pos"))
    if len(position) != 3:
        raise ValueError("compiled graph position must have three coordinates")
    for coordinate in position:
        _number(coordinate, positive=False)
    return _name(row.get("node_id"))


def _arc(value: object) -> Arc:
    row = _object(value)
    length, cost = _number(row.get("length_m")), _number(row.get("cost_m"))
    if length != cost:
        raise ValueError("compiled V3 route cost must equal declared length in metres")
    return Arc(
        _name(row.get("arc_id")),
        _name(row.get("from_node_id")),
        _name(row.get("to_node_id")),
        length,
        cost,
        modes=_names(row, "allowed_modes"),
        profiles=_names(row, "allowed_geometry_profile_ids"),
        cargo_classes=_cargo(row),
        clear_width_m=_width(row),
        clear_height_m=_number(row["clear_height_m"]) if "clear_height_m" in row else None,
    )


def compiled_graph(document: Mapping[str, object], graph_id: str) -> DirectedGraph:
    """Use already compiled arcs, never raw unsplit L06/L07 edges or implicit reverse arcs."""
    if document.get("layout_version") != LAYOUT_VERSION or graph_id not in {"walk", "vehicle"}:
        raise ValueError("unsupported compiled V3 layout or graph selector")
    graph = _object(document.get(graph_id + "_graph"))
    return DirectedGraph(
        graph_id,
        (_node(row) for row in _array(graph.get("nodes"))),
        (_arc(row) for row in _array(graph.get("arcs"))),
    )
