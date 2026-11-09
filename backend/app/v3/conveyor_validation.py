"""Fail-closed reference and capacity checks for the supported L08 source model."""

from collections import Counter
from typing import Any

from app.v3.conveyor_models import ConveyorSource

ALLOWED_KINDS = ("order_tote", "sealed_parcel", "SMALL_CARTON", "STANDARD_CARTON")


def validate_references(source: ConveyorSource) -> None:
    for edge in source.edges.values():
        if edge.source not in source.nodes or edge.target not in source.nodes:
            raise ValueError("Unknown edge node")
        if edge.resource_id not in source.resources:
            raise ValueError("Unknown edge resource")
        turn_endpoint = edge.source if edge.turn_timing == "before_edge" else edge.target
        if edge.turn_node_id is not None and edge.turn_node_id != turn_endpoint:
            raise ValueError("Pivot must use correct edge endpoint")
    for station in source.stations.values():
        if station.work_node_id not in source.nodes:
            raise ValueError("Unknown station work node")
        resource = source.resources.get(station.spur_resource_id)
        if resource is None or not resource.exclusive:
            raise ValueError("Station needs known exclusive spur")
    validate_resources(source)


def validate_resources(source: ConveyorSource) -> None:
    memberships = Counter(c for r in source.resources.values() for c in r.cell_ids)
    if memberships != Counter({c: 1 for c in source.cells}):
        raise ValueError("Resources must partition all source cells exactly once")
    for resource in source.resources.values():
        if resource.exclusive and resource.capacity != 1:
            raise ValueError("Unsupported shared exclusive capacity")
        if not resource.exclusive and resource.capacity != len(resource.cell_ids):
            raise ValueError("Cell-collection capacity must equal member count")
        for cell_id in resource.cell_ids:
            cell = source.cells[cell_id]
            if cell.resource_id != resource.resource_id or cell.capacity != 1:
                raise ValueError("Cell resource/capacity mismatch")


def validate_policy(document: dict[str, Any]) -> None:
    payload = document["payload_admission"]
    if tuple(payload["allowed"]) != ALLOWED_KINDS:
        raise ValueError("Unsupported payload-kind policy")
    if document["layout_version"] != "qoima-144x72-v3-proposal":
        raise ValueError("Unsupported conveyor layout version")
    if document["not_an_actual_engine_run"] is not True:
        raise ValueError("Source conveyor must remain a static proposal")
    if document["units"] != {"length": "m", "time": "s", "up_axis": "Y"}:
        raise ValueError("Unsupported source units")
