"""Pinned L08/C02 source oracles established before the connected engine is inspected."""

import json
from fractions import Fraction as F
from functools import cache
from itertools import pairwise
from pathlib import Path
from typing import Any, cast


@cache
def source_document(name: str) -> dict[str, Any]:
    root = Path("data/v3-proposal/docs/v3/contract-proposals")
    return cast(dict[str, Any], json.loads((root / name).read_text(encoding="utf-8")))


def test_l08_physical_handoff_points_and_pedestrian_only_terminal_modes() -> None:
    graph = source_document("layout-links-v3.json")["walk_graph"]
    nodes = {n["node_id"]: n for n in graph["nodes"]}
    expected = {
        "CART_PARK": [131.25, 0, 7.1],
        "CONVEYOR_IN": [129.75, 0, 5.8],
        "CONVEYOR_OUT": [55, 0, 3],
        "OUT_S_EXPRESS": [48, 0, 6],
        **{f"PK{i:02}": [51 + 11 * i, 0, 6.1] for i in range(1, 7)},
    }
    for name, position in expected.items():
        assert nodes["v3:service:" + name]["world_pos"] == position
    pedestrian_only = {"v3:service:CONVEYOR_IN", "v3:service:CONVEYOR_OUT"}
    pedestrian_only |= {f"v3:service:PK{i:02}" for i in range(1, 7)}
    for arc in graph["arcs"]:
        if {arc["from_node_id"], arc["to_node_id"]} & pedestrian_only:
            assert arc["allowed_modes"] == ["pedestrian"]


def test_both_l08_splits_of_one_corridor_survive_in_one_continuous_chain() -> None:
    graph = source_document("layout-links-v3.json")["walk_graph"]
    group = next(g for g in graph["split_groups"] if g["original_edge_id"] == "v3:ped-edge:0046")
    assert [s["compiled_node_id"] for s in group["ordered_splits"]] == [
        "v3:ped-node:12975:01000",
        "v3:ped-node:13125:01000",
    ]
    arcs = {a["arc_id"]: a for a in graph["arcs"]}
    chain = [arcs[f"v3:ped-edge:0046:part:{i:03}:f"] for i in range(3)]
    assert [chain[0]["from_node_id"], *(a["to_node_id"] for a in chain)] == [
        "v3:ped-node:11700:01000",
        "v3:ped-node:12975:01000",
        "v3:ped-node:13125:01000",
        "v3:ped-node:13800:01000",
    ]
    assert all(a["to_node_id"] == b["from_node_id"] for a, b in pairwise(chain))
    assert len(graph["source_edge_arc_map"]["v3:ped-edge:0046"]) == 6
    for index, forward in enumerate(chain):
        reverse = arcs[f"v3:ped-edge:0046:part:{index:03}:r"]
        assert reverse["from_node_id"] == forward["to_node_id"]
        assert reverse["to_node_id"] == forward["from_node_id"]
        assert reverse["source_u_range"] == forward["source_u_range"][::-1]


def test_cart_park_to_intake_has_explicit_corridor_path_not_direct_teleport() -> None:
    graph = source_document("layout-links-v3.json")["walk_graph"]
    arcs = {a["arc_id"]: a for a in graph["arcs"]}
    path = [
        arcs[k]
        for k in (
            "v3:service:CART_PARK:segment:000:r",
            "v3:ped-edge:0046:part:001:r",
            "v3:service:CONVEYOR_IN:segment:000:f",
        )
    ]
    assert path[0]["from_node_id"] == "v3:service:CART_PARK"
    assert path[-1]["to_node_id"] == "v3:service:CONVEYOR_IN"
    assert all(a["to_node_id"] == b["from_node_id"] for a, b in pairwise(path))
    assert all("pedestrian" in a["allowed_modes"] for a in path)
    assert "manual_cart" not in path[-1]["allowed_modes"]
    # Nominal geometry2.9+1.5+4.2; preserve serialized source residuals exactly.
    assert [F(str(a["length_m"])) for a in path] == [
        F("2.9000000000000004"),
        F("1.4999999999879994"),
        F("4.2"),
    ]


def test_small_unit_and_parent_wrapper_mass_are_distinct_source_quantities() -> None:
    catalog = source_document("cargo-catalog-v3.json")
    small = next(r for r in catalog["records"] if r["archetype_id"] == "SMALL_CARTON")
    unit, hu = small["unit"], small["handling_unit"]
    assert F(str(unit["gross_mass_kg"])) == F(7, 200)
    assert F(str(unit["contents_mass_kg"])) + F(str(unit["packaging_tare_mass_kg"])) == F(7, 200)
    assert hu["units_per_handling_unit"] == 24
    assert F(str(hu["packaging_tare_mass_kg"])) == F(1, 10)
    assert F(str(hu["gross_mass_kg"])) == 24 * F(7, 200) + F(1, 10) == F(47, 50)


def test_express_handoff_service_uses_declared_per_hu_capacity_and_clock() -> None:
    ports = source_document("ports-v3.outbound.json")["ports"]
    express = next(port for port in ports if port["port_id"] == "OUT_S_EXPRESS")
    assert express["service_node_world_pos"] == [48, 0, 6]
    assert express["service_capacity"]["max_concurrent_jobs"] == 1
    assert express["service_time_rule"]["seconds_by_archetype"]["SMALL_CARTON"] == 20
    assert express["open_windows"] == [[0, 28800]]
    assert express["finite_buffer_capacity"]["total"] == 8
