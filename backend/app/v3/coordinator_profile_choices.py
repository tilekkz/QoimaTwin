"""Canonical sets and generated legacy aliases never create extra resources."""

from copy import deepcopy
from typing import Any

from app.v3.flow_profile_wire import normalized_choices
from app.v3.staff_registry import compile_staff_registry, registry_document
from app.v3.whole_profile_io_choices import normalize as whole_normalize

TABLES = (
    ("goods_stations", "station_id"),
    ("carts", "cart_id"),
    ("picker_bindings", "actor_id"),
    ("parcel_ports", "port_id"),
    ("unit_assignments", "order_id"),
    ("role_intents", "intent_id"),
)


def normalized(value: dict[str, Any]) -> dict[str, Any]:
    result = normalized_choices(value)
    for key, identity in TABLES:
        indexed(result[key], identity)
        result[key].sort(key=lambda row: row[identity])
    for row in result["picker_bindings"]:
        row["cart_ids"].sort()
    result["registry"] = registry_document(compile_staff_registry(result["registry"]))
    # Reuse all shared whole/receipt uniqueness, clocks and buffer checks.
    common = whole_normalize(legacy_choices(result))
    for key in (
        "actors",
        "owners",
        "materials",
        "recipes",
        "orders",
        "receipts",
        "receipt_ports",
        "receipt_buffers",
        "whole_orders",
        "whole_ports",
        "whole_buffers",
    ):
        result[key] = common[key]
    return result


def indexed(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    result = {row[key]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError(f"Duplicate declared {key}")
    return result


def legacy_choices(value: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(value)
    try:
        cart = min(value["carts"], key=lambda row: row["cart_id"])
        port = min(value["parcel_ports"], key=lambda row: row["port_id"])
        station_id = next(
            row["station_id"]
            for row in value["registry"]["station_bindings"]
            if row["primary_actor_id"] == "K06"
        )
        station = indexed(value["goods_stations"], "station_id")[station_id]
    except (KeyError, ValueError, StopIteration) as exc:
        raise ValueError("Declared resources cannot form an internal compatibility view") from exc
    result["roles"] = dict(picker_id="P01", packer_id="K06", shipper_id="S01")
    result["cart"] = {
        k: v for k, v in cart.items() if k not in {"carrier_pool_owner", "release_tick"}
    }
    result["station"] = {k: v for k, v in station.items() if k != "package_pool_owner"}
    result["port_id"] = port["port_id"]
    result["pool_owners"] = dict(
        carrier=cart["carrier_pool_owner"],
        package=station["package_pool_owner"],
        shipped=port["shipped_owner"],
    )
    return result
