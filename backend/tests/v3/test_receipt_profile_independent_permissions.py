"""Typed routing must actually obey explicit denial after the C09 absence projection."""

from copy import deepcopy
from fractions import Fraction as F
from typing import Any

from app.v3.receipt_profile_permissions import project_manual_cargo
from app.v3.runtime_graph import RouteRequirements
from app.v3.runtime_graph_source import compiled_graph


def links_fixture() -> dict[str, Any]:
    arcs: list[dict[str, Any]] = []
    for key, source, target, length in (
        ("deny", "A", "C", 1),
        ("ab", "A", "B", 2),
        ("bc", "B", "C", 3),
    ):
        arcs.append(
            {
                "arc_id": key,
                "from_node_id": source,
                "to_node_id": target,
                "length_m": length,
                "cost_m": length,
                "width_m": 0.7,
                "clear_height_m": 2,
                "allowed_modes": ["pedestrian"],
            }
        )
    arcs[0]["cargo_transport_supported"] = False
    return {
        "layout_version": "qoima-144x72-v3-proposal",
        "walk_graph": {
            "nodes": [{"node_id": k, "world_pos": [i, 0, 0]} for i, k in enumerate("ABC")],
            "arcs": arcs,
        },
        "vehicle_graph": {"arcs": [{"cargo_transport_supported": False}]},
    }


def test_projection_keeps_denied_shortcut_blocked_and_preserves_all_other_graph_fields() -> None:
    original = links_fixture()
    links = deepcopy(original)
    project_manual_cargo(links)
    graph = compiled_graph(links, "walk")
    required = RouteRequirements(mode="pedestrian", cargo="SMALL_CARTON", min_clear_width_m=F(".6"))
    route = graph.shortest_path("A", "C", required)
    assert route is not None and route.arc_ids == ("ab", "bc") and route.length_m == 5
    assert links["vehicle_graph"] == original["vehicle_graph"]
    assert links["walk_graph"]["nodes"] == original["walk_graph"]["nodes"]
    assert links["walk_graph"]["arcs"][0] == original["walk_graph"]["arcs"][0]
    links["walk_graph"]["arcs"][2]["allowed_cargo_archetype_ids"] = []
    project_manual_cargo(links)
    assert compiled_graph(links, "walk").shortest_path("A", "C", required) is None
    assert graph.shortest_path("A", "C", replace_width(required)) is None


def replace_width(required: RouteRequirements) -> RouteRequirements:
    return RouteRequirements(
        mode=required.mode, cargo=required.cargo, min_clear_width_m=F(".700001")
    )
