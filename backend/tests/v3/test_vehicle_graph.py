"""Directed source projection and analytical pose checks from hand geometry."""

import math
from fractions import Fraction as F

import pytest

from app.v3.vehicle_geometry import pose_at
from app.v3.vehicle_graph import decode_vehicle_graph
from tests.v3.test_vehicle_fixtures import graph_documents


def test_fields_traffic_and_fractional_pose_are_preserved() -> None:
    docs = graph_documents()
    graph = decode_vehicle_graph(docs["layout"], docs["traffic"], docs["vehicle"])
    arc = graph.arcs["AB"]
    assert arc.equipment_pairs == frozenset({"INBOUND_FORKLIFT_PAIR"})
    assert arc.source_groups == ("junction",)
    assert arc.traffic_groups == ("shared",)
    assert arc.clear_width_m is None
    assert arc.clearance_ref == "declared component sweep"
    assert graph.resources["shared"].human_route_refs == ("walk",)
    assert arc.front_axle_length_m == arc.root_length_m == F(2)
    pose = pose_at(arc.geometry, F(1, 2), graph.axle_offset_m)
    assert pose.root_xyz == pytest.approx((0, 0, 1))
    assert pose.yaw_rad == 0
    with pytest.raises(TypeError):
        graph.arcs["other"] = arc  # type: ignore[index]


def test_reverse_is_explicit_and_does_not_flip_physical_yaw() -> None:
    docs = graph_documents()
    arc = docs["layout"]["vehicle_graph"]["arcs"][0]
    arc.update(arc_id="BA", from_node_id="B", to_node_id="A", motion_direction=-1)
    arc["geometry"].update(front_axle_start_xz_m=[0, 2.4], front_axle_end_xz_m=[0, 0.4])
    docs["layout"]["traffic_route_bindings"][0]["compiled_arc_ids"] = ["BA"]
    graph = decode_vehicle_graph(docs["layout"], docs["traffic"], docs["vehicle"])
    assert tuple(graph.arcs) == ("BA",)
    assert pose_at(graph.arcs["BA"].geometry, F(1), graph.axle_offset_m).yaw_rad == 0


def test_turn_uses_analytic_arc_not_chord_and_retains_unwrapped_yaw() -> None:
    from app.v3.vehicle_types import ArcGeometry

    curve = ArcGeometry(
        "rear_steer_arc", F(0), F(str(math.pi / 2)), icr_xz=(F(0), F(0)), signed_radius_m=F(1)
    )
    pose = pose_at(curve, F(1, 2), F("0.4"))
    q = math.sqrt(0.5)
    assert pose.front_axle_xyz == pytest.approx((-q, 0, q))
    assert pose.root_xyz == pytest.approx((-1.4 * q, 0, 0.6 * q))
    assert pose.yaw_rad == pytest.approx(math.pi / 4)
    with pytest.raises(ValueError, match="progress"):
        pose_at(curve, F(2), F("0.4"))


@pytest.mark.parametrize("mutation", ["motion", "pose", "length", "pair", "group", "binding"])
def test_malformed_source_is_rejected(mutation: str) -> None:
    docs = graph_documents()
    arc = docs["layout"]["vehicle_graph"]["arcs"][0]
    if mutation == "motion":
        arc["motion_direction"] = -1
    elif mutation == "pose":
        docs["layout"]["vehicle_graph"]["nodes"][1]["yaw_rad"] = 1
    elif mutation == "length":
        arc["length_m"] = 3
    elif mutation == "pair":
        arc["equipment_pair_refs"] = ["invented"]
    elif mutation == "group":
        arc["source_reservation_group_ids"] = ["missing"]
    else:
        docs["layout"]["traffic_route_bindings"][0]["compiled_arc_ids"] = ["missing"]
    with pytest.raises(ValueError):
        decode_vehicle_graph(docs["layout"], docs["traffic"], docs["vehicle"])
