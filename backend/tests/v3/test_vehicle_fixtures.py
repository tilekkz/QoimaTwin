"""Hand geometry and declared evidence, never actual mesh certification."""

from fractions import Fraction as F
from typing import Any


def hand_arc() -> dict[str, Any]:
    return {
        "arc_id": "AB",
        "from_node_id": "A",
        "to_node_id": "B",
        "geometry": {
            "kind": "line",
            "front_axle_start_xz_m": [0, 0.4],
            "front_axle_end_xz_m": [0, 2.4],
            "start_yaw_rad": 0,
            "end_yaw_rad": 0,
        },
        "motion_direction": 1,
        "front_axle_path_length_m": 2,
        "length_m": 2,
        "cost_m": 2,
        "allowed_geometry_profile_ids": ["nonlong_forklift"],
        "allowed_cargo_archetype_ids": ["PALLET_LOAD"],
        "equipment_pair_refs": ["INBOUND_FORKLIFT_PAIR"],
        "source_reservation_group_ids": ["junction"],
        "clear_height_m": 8,
        "clearance_ref": "declared component sweep",
        "source": "hand",
        "source_path_id": "local",
        "rear_virtual_steer_deg": 0,
        "curvature_transition": "stop and set steering",
    }


def graph_documents() -> dict[str, Any]:
    nodes = [
        {"node_id": "A", "world_pos": [0, 0, 0], "front_axle_world_pos": [0, 0, 0.4], "yaw_rad": 0},
        {"node_id": "B", "world_pos": [0, 0, 2], "front_axle_world_pos": [0, 0, 2.4], "yaw_rad": 0},
    ]
    layout = {
        "layout_version": "hand",
        "vehicle_graph": {"nodes": nodes, "arcs": [hand_arc()], "front_axle_root_offset_m": 0.4},
        "traffic_route_bindings": [
            {"route_ref": "local", "compiled_graph": "vehicle", "compiled_arc_ids": ["AB"]}
        ],
    }
    traffic = {
        "layout_version": "hand",
        "mixed_traffic": {
            "resources": [
                {
                    "resource_id": "shared",
                    "capacity_occupants": 1,
                    "vehicle_route_refs": ["local"],
                    "human_route_refs": ["walk"],
                }
            ]
        },
    }
    vehicle = {
        "layout_version": "hand",
        "equipment_pair_refs": ["INBOUND_FORKLIFT_PAIR"],
        "reservation_groups": [{"reservation_group_id": "junction", "capacity_vehicles": 1}],
    }
    return {"layout": layout, "traffic": traffic, "vehicle": vehicle}


def fraction(value: int | str) -> F:
    return F(value)


def source_load() -> dict[str, Any]:
    """C08 PALLET fields; numbers are copied from the pinned source design, not engine output."""
    return {
        "archetype_id": "PALLET_LOAD",
        "scale_factor": 1,
        "HU_gross_mass_kg": 455,
        "attachment_mass_kg": 0,
        "total_lifted_mass_kg": 455,
        "cog_local_xyz_m": [0, 1.375, 1],
        "fork_centres_x_m": [-0.4, 0.4],
        "extended_handling_rating_arm_from_fixed_Z04_m": 1,
        "fork_top_travel_y_m": 0.7,
        "cargo_bounds_local_m": {"min": [-0.6, 0.7, 0.5]},
        "handling_unit_dimensions_xyz_m": [1.2, 1.35, 1],
        "local_geometry_profile_id": "nonlong_forklift",
    }


def source_handling() -> dict[str, Any]:
    return {
        "layout_content_hash": "hand-layout",
        "rating_design": {
            "nominal_capacity_kg": 1000,
            "moment_budget_kg_m": 800,
            "maximum_single_fork_share_kg": 500,
            "maximum_fork_top_handling_y_m": 1.5,
            "rating_reference_z_m": 0.4,
        },
        "stopped_reach_handling_design": {"minimum_fork_top_y_m": 0.18, "extension_m": 0.4},
        "fork_design": {"width_each_m": 0.08, "thickness_m": 0.07},
        "per_cargo_arc_eligibility": [{"archetype_id": "PALLET_LOAD", "allowed_arc_ids": ["AB"]}],
        "loads": [source_load()],
        "ports": [
            {
                "port_id": "IN_W_BULK",
                "equipment_pair_ref": "INBOUND_FORKLIFT_PAIR",
                "forklift_cargo_archetype_ids": ["PALLET_LOAD"],
            }
        ],
    }


def source_documents() -> dict[str, Any]:
    graph = graph_documents()
    slot = {
        "slot_id": "slot",
        "access": {"vehicle": "B"},
        "reserve_only": False,
        "retrieval_blocked": False,
        "usable_dimensions_xyz_m": [1.4, 1.5, 1.2],
        "service_height_m": 0.18,
        "clearance_each_side_m": 0.05,
        "max_payload_kg": 1000,
        "allowed_cargo_archetype_ids": ["PALLET_LOAD"],
    }
    return {
        "layout-links-v3.json": graph["layout"],
        "layout-conflicts-v3.json": graph["traffic"],
        "vehicle-graph-v3.json": graph["vehicle"],
        "vehicle-handling-v3.json": source_handling(),
        "storage-slots-v3.json": {"slots": [slot]},
        "port-resource-policy-v3.json": {
            "forklift_pairs": [
                {"pair_id": "INBOUND_FORKLIFT_PAIR", "actor_id": "F01", "vehicle_id": "FL01"}
            ]
        },
    }
