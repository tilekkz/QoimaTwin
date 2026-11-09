"""New proposal choices; old whole/light schemas remain unchanged."""

from functools import cache
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

from app.storage.canonical_json import canonical_bytes
from app.v3.coordinator_profile_staff_schema import registry_schema
from app.v3.flow_profile_schema import TEXT, TICK, array_schema, object_schema
from app.v3.receipt_profile_schema import _exact
from app.v3.whole_profile_schema import whole_profile_schema

SCHEMA_ID = "qoima.coordinator-profile.v3-proposal"
SCHEMA_VERSION = "0.1.0"
ALIASES = ("roles", "cart", "station", "port_id", "pool_owners")
ASSIGNMENT = ("picker_id", "cart_id", "station_id", "shipper_id", "port_id")


def coordinator_profile_schema() -> dict[str, Any]:
    schema = whole_profile_schema()
    schema["$id"] = SCHEMA_ID
    schema["properties"]["schema_id"] = {"const": SCHEMA_ID}
    schema["properties"]["schema_version"] = {"const": SCHEMA_VERSION}
    for key in ALIASES:
        del schema["properties"][key]
        schema["required"].remove(key)
    cart = schema["$defs"]["cart"]
    cart["properties"].update(carrier_pool_owner=TEXT, release_tick=TICK)
    cart["required"].extend(["carrier_pool_owner", "release_tick"])
    schema["$defs"].update(_definitions())
    additions = {
        "registry": registry_schema(),
        "goods_stations": array_schema("goods_station"),
        "carts": array_schema("cart"),
        "picker_bindings": array_schema("picker_binding"),
        "parcel_ports": array_schema("parcel_port"),
        "unit_assignments": array_schema("unit_assignment"),
        "role_intents": array_schema("role_intent"),
    }
    schema["properties"].update(additions)
    schema["required"].extend(additions)
    return schema


def _definitions() -> dict[str, Any]:
    return {
        "goods_station": object_schema(
            {
                key: TEXT
                for key in ("station_id", "bench_owner", "empty_owner", "package_pool_owner")
            }
        ),
        "picker_binding": object_schema(
            {"actor_id": TEXT, "cart_ids": {"type": "array", "items": TEXT, "uniqueItems": True}}
        ),
        "parcel_port": object_schema({"port_id": TEXT, "shipped_owner": TEXT}),
        "unit_assignment": object_schema({key: TEXT for key in ("order_id", *ASSIGNMENT)}),
        "role_intent": object_schema(
            {
                "intent_id": TEXT,
                "actor_id": TEXT,
                "station_id": TEXT,
                "request_tick": TICK,
                "return_tick": TICK,
                "restore_by_tick": TICK,
            }
        ),
    }


@cache
def _validator() -> Draft202012Validator:
    schema = coordinator_profile_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_document(value: Any) -> None:
    canonical_bytes(value)
    _exact(value)
    try:
        _validator().validate(value)
    except ValidationError as exc:
        path = "/".join(map(str, exc.absolute_path))
        raise ValueError(f"Invalid coordinator profile at {path}: {exc.message}") from exc
