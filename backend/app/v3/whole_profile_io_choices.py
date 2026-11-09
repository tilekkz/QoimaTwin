"""Normalize only unordered public tables; keep geometric paths and unit placements ordered."""

from typing import Any

from app.v3.flow_profile_wire import normalized_choices

TABLES = (
    ("actors", "actor_id"),
    ("owners", "owner_id"),
    ("recipes", "recipe_id"),
    ("materials", "container_id"),
    ("orders", "order_id"),
    ("receipts", "receipt_id"),
    ("receipt_ports", "port_id"),
    ("receipt_buffers", "owner_id"),
    ("whole_orders", "job_id"),
    ("whole_ports", "port_id"),
    ("whole_buffers", "owner_id"),
)


def normalize(document: dict[str, Any]) -> dict[str, Any]:
    value = normalized_choices(document)
    for key, identity in TABLES:
        if len({row[identity] for row in value[key]}) != len(value[key]):
            raise ValueError(f"Duplicate {key} identity")
        value[key].sort(key=lambda row: row[identity])
    for prefix, actors in (("receipt", "receiver_ids"), ("whole", "shipper_ids")):
        for port in value[prefix + "_ports"]:
            port[actors].sort()
            port["buffer_owner_ids"].sort()
        _buffers(value, prefix)
    _clocks(value)
    future = {row["hu_id"] for row in value["receipts"]}
    if any(order["source_hu"] in future for order in value["orders"]):
        raise ValueError("Whole public unit orders require original baseline SMALL stock")
    return value


def _buffers(value: dict[str, Any], prefix: str) -> None:
    selected: dict[str, str] = {}
    for port in value[prefix + "_ports"]:
        for key in port["buffer_owner_ids"]:
            if key in selected:
                raise ValueError("Buffer belongs to multiple ports")
            selected[key] = port["port_id"]
    declared = {row["owner_id"]: row["port_id"] for row in value[prefix + "_buffers"]}
    if selected != declared:
        raise ValueError("Every buffer must belong to its selected source port")


def _clocks(value: dict[str, Any]) -> None:
    horizon, end = value["horizon_tick"], value["end_tick"]
    if end < horizon:
        raise ValueError("Whole clock requires H <= end")
    offers = (*value["orders"], *value["receipts"], *value["whole_orders"])
    if any(row["arrival_tick"] >= horizon for row in offers):
        raise ValueError("Every offered arrival must be in [0,H)")
