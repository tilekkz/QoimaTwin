"""Exact first-arc prerequisites after authenticated E011 pickup inputs."""

from typing import Any

from app.v3.pallet_outbound_pickup_identity import require
from app.v3.pallet_outbound_pickup_models import PickupSource
from app.v3.pallet_outbound_pickup_plan import selected
from app.v3.pallet_outbound_pickup_source import document


def arc_facts(source: PickupSource) -> dict[str, Any]:
    facts = selected(source)
    arc, pair = facts["arc"], facts["pair"]
    handling = document(source, "vehicle-handling-v3.json", "v3-vehicle-proposal")
    eligible = next(
        row for row in handling["per_cargo_arc_eligibility"] if row["archetype_id"] == "PALLET_LOAD"
    )["allowed_arc_ids"]
    require(
        arc["arc_id"] in eligible
        and "PALLET_LOAD" in arc["allowed_cargo_archetype_ids"]
        and arc["cargo_transport_supported"] is True,
        "Original loaded cargo eligibility required",
    )
    require(
        pair["pair_id"] in arc["equipment_pair_refs"] and pair["eligible_direction"] == "outbound",
        "Original outbound pair eligibility required",
    )
    require(
        facts["load"]["local_geometry_profile_id"] in arc["allowed_geometry_profile_ids"],
        "Original component geometry profile required",
    )
    geometry = arc["geometry"]
    require(
        geometry["kind"] == "line"
        and arc["motion_direction"] == -1
        and geometry["start_yaw_rad"] == geometry["end_yaw_rad"] == facts["node"]["yaw_rad"]
        and geometry["rear_virtual_steer_deg"] == 0,
        "Only first straight reverse arc supported",
    )
    graph = document(source, "layout-links-v3.json")["vehicle_graph"]
    end = next(node for node in graph["nodes"] if node["node_id"] == arc["to_node_id"])
    profiles = document(source, "vehicle-graph-v3.json", "v3-vehicle-proposal")["profiles"]
    top = next(row["top_padding_m"] for row in profiles if row["profile_id"] == "loaded_max")
    require(arc["clearance_padding_m"] == top == 0.25, "Original XZ/top padding required")
    require(
        end.get("stop_allowed") is None, "Unknown destination stop permission must remain unknown"
    )
    return {**facts, "end_node": end, "top_padding": top}
