"""Current cargo places; completed deliveries are not retained as snapshot history."""

from typing import Any


def apply_position(positions: dict[str, Any], event: dict[str, Any]) -> None:
    p, kind = event["payload"], event["kind"]
    if kind == "cargo_placed":
        positions[p["cargo_id"]] = {
            "container_id": p["container_id"],
            "slot_index": p["slot_index"],
            "vehicle_id": None,
        }
    elif kind == "cargo_removed":
        if positions.get(p["cargo_id"], {}).get("container_id") == p["container_id"]:
            positions.pop(p["cargo_id"], None)
    elif kind == "cargo_attached":
        positions[p["cargo_id"]] = {
            "container_id": None,
            "slot_index": None,
            "vehicle_id": p["vehicle_id"],
        }
    elif kind == "cargo_detached":
        previous = positions.get(p["cargo_id"], {})
        slot = (
            previous.get("slot_index")
            if previous.get("container_id") == p["container_id"]
            else None
        )
        positions[p["cargo_id"]] = {
            "container_id": p["container_id"],
            "slot_index": slot,
            "vehicle_id": None,
        }
    elif kind == "order_dispatched":
        positions.pop(p["pallet_id"], None)
