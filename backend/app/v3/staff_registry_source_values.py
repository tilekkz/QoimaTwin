"""Source-only station anchors; worker service and cargo WORK nodes stay distinct."""

from fractions import Fraction
from typing import Any

from app.v3.staff_registry_models import StaffStation

Point = tuple[Fraction, Fraction, Fraction]


def _point(values: list[int | float]) -> Point:
    return Fraction(str(values[0])), Fraction(str(values[1])), Fraction(str(values[2]))


def positions(links: dict[str, Any]) -> dict[str, Point]:
    return {
        n["node_id"]: _point(n["world_pos"])
        for n in links["walk_graph"]["nodes"]
        if n.get("allowed_modes") == ["pedestrian"]
    }


def source_stations(
    conveyor: dict[str, Any], workers: dict[str, Point]
) -> tuple[StaffStation, ...]:
    cargo = {n["node_id"]: _point(n["world_pos"]) for n in conveyor["nodes"]}
    stations = []
    for row in conveyor["packing_stations"]:
        service = "v3:service:" + row["pack_id"]
        worker_position = _point(row["worker_service"])
        if workers.get(service) != worker_position:
            raise ValueError("STAFF_SERVICE_ANCHOR_MISMATCH")
        stations.append(
            StaffStation(
                row["pack_id"],
                service,
                worker_position,
                row["work_node_id"],
                cargo[row["work_node_id"]],
                row["spur_resource_id"],
            )
        )
    return tuple(sorted(stations, key=lambda s: s.station_id))
