"""Compiled-source boundary validates geometry costs and preserves explicit directed arcs."""

from copy import deepcopy
from typing import Any

import pytest

from app.v3.runtime_graph import RouteRequirements
from app.v3.runtime_graph_source import compiled_graph


def document() -> dict[str, Any]:
    return {
        "layout_version": "qoima-144x72-v3-proposal",
        "operational_admission": False,
        "walk_graph": {
            "nodes": [
                {"node_id": "a", "world_pos": [0, 0, 0]},
                {"node_id": "b", "world_pos": [1, 0, 0]},
            ],
            "arcs": [
                {
                    "arc_id": "ab",
                    "from_node_id": "a",
                    "to_node_id": "b",
                    "length_m": 1,
                    "cost_m": 1,
                    "allowed_modes": ["pedestrian"],
                    "width_m": 2,
                    "clear_height_m": 3,
                }
            ],
        },
    }


def test_source_is_read_only_and_does_not_gain_reverse_arcs() -> None:
    source = document()
    before = deepcopy(source)
    graph = compiled_graph(source, "walk")
    assert graph.graph_id == "walk"
    assert graph.shortest_path("a", "b", RouteRequirements(mode="pedestrian")) is not None
    assert graph.shortest_path("a", "b", RouteRequirements(mode="manual_cart")) is None
    assert graph.shortest_path("b", "a") is None
    assert source == before


@pytest.mark.parametrize(
    "key,value",
    [
        ("from_node_id", "missing"),
        ("cost_m", -1),
        ("cost_m", 0.5),
        ("length_m", float("nan")),
        ("width_m", True),
        ("allowed_modes", "pedestrian"),
        ("allowed_modes", ["pedestrian", "pedestrian"]),
    ],
)
def test_bad_declared_arc_is_rejected(key: str, value: object) -> None:
    source = document()
    source["walk_graph"]["arcs"][0][key] = value
    with pytest.raises(ValueError):
        compiled_graph(source, "walk")


@pytest.mark.parametrize("position", [[0, 0], [0, float("inf"), 0], [True, 0, 0]])
def test_bad_source_position_is_rejected(position: object) -> None:
    source = document()
    source["walk_graph"]["nodes"][0]["world_pos"] = position
    with pytest.raises(ValueError):
        compiled_graph(source, "walk")


def test_graph_namespace_is_explicit() -> None:
    source = document()
    source["vehicle_graph"] = deepcopy(source["walk_graph"])
    assert compiled_graph(source, "walk").node_ids == compiled_graph(source, "vehicle").node_ids
    with pytest.raises(ValueError):
        compiled_graph(source, "unknown")


def test_source_layout_is_not_silently_relabelled_v2() -> None:
    source = document()
    source["layout_version"] = "qoima-72x48-v2"
    with pytest.raises(ValueError):
        compiled_graph(source, "walk")


@pytest.mark.parametrize("support", [False, "yes", None])
def test_cargo_permission_cannot_override_unsupported_or_malformed_flag(support: object) -> None:
    source = document()
    arc = source["walk_graph"]["arcs"][0]
    arc["allowed_cargo_archetype_ids"] = ["HEAVY_BOX"]
    arc["cargo_transport_supported"] = support
    with pytest.raises(ValueError):
        compiled_graph(source, "walk")
