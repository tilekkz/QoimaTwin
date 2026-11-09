"""Versioned strict public choice schema; no derived geometry or hidden defaults."""

from functools import cache
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

from app.storage.canonical_json import canonical_bytes
from app.v3.input_pin import LAYOUT_CONTENT_HASH, SOURCE_REVISION

SCHEMA_ID = "qoima.light-flow-profile.v3-proposal"
SCHEMA_VERSION = "0.1.0"
TEXT = {"type": "string", "minLength": 1, "pattern": r"\S"}
TICK = {"type": "integer", "minimum": 0}
POSITIVE = {"type": "integer", "minimum": 1}
RATIONAL = {"$ref": "#/$defs/rational"}
VECTOR = {"$ref": "#/$defs/vector"}
TIME_FIELDS = ("attach", "pick_per_unit", "park", "detach", "deposit", "pack", "clear", "pickup")


def object_schema(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def array_schema(item: str) -> dict[str, Any]:
    return {"type": "array", "items": {"$ref": "#/$defs/" + item}}


def _physical_definitions() -> dict[str, Any]:
    return {
        "recipe": object_schema(
            {
                "recipe_id": TEXT,
                "provenance": TEXT,
                "kind": {"enum": ["carrier", "package"]},
                "outer": VECTOR,
                "inner": VECTOR,
                "tare_kg": RATIONAL,
                "max_gross_kg": RATIONAL,
                "max_units": POSITIVE,
                "allowed_archetypes": {
                    "type": "array",
                    "items": TEXT,
                    "minItems": 1,
                    "uniqueItems": True,
                },
                "clearance_m": RATIONAL,
            }
        ),
        "owner": object_schema(
            {
                "owner_id": TEXT,
                "kind": {"enum": ["material", "workstation", "shipped", "disposal"]},
                "capacity": POSITIVE,
            }
        ),
        "material": object_schema(
            {
                "container_id": TEXT,
                "recipe_id": TEXT,
                "owner_id": TEXT,
                "sealed_for": {"type": "null"},
            }
        ),
        "placement": object_schema({"unit_id": TEXT, "position": VECTOR}),
    }


def _definitions() -> dict[str, Any]:
    return {
        **_physical_definitions(),
        "cart": _cart_schema(),
        "rational": object_schema({"numerator": {"type": "integer"}, "denominator": POSITIVE}),
        "vector": {"type": "array", "minItems": 3, "maxItems": 3, "items": RATIONAL},
        "actor": object_schema(
            {
                "actor_id": TEXT,
                "home": TEXT,
                "speed_m_s": RATIONAL,
                "max_gross_kg": RATIONAL,
                "available_tick": TICK,
            }
        ),
        "order": object_schema(
            {
                "order_id": TEXT,
                "arrival_tick": TICK,
                "source_hu": TEXT,
                "carrier_id": TEXT,
                "package_id": TEXT,
                "carrier_placements": array_schema("placement"),
                "package_placements": array_schema("placement"),
            }
        ),
    }


def _cart_schema() -> dict[str, Any]:
    return object_schema(
        {
            "cart_id": TEXT,
            "home": TEXT,
            "owner_id": TEXT,
            "speed_m_s": RATIONAL,
            "max_gross_kg": RATIONAL,
            "width_m": RATIONAL,
        }
    )


def profile_schema() -> dict[str, Any]:
    result = object_schema(
        {
            "schema_id": {"const": SCHEMA_ID},
            "schema_version": {"const": SCHEMA_VERSION},
            "source": object_schema(
                {
                    "revision": {"const": SOURCE_REVISION},
                    "layout_content_hash": {"const": LAYOUT_CONTENT_HASH},
                }
            ),
            "profile_id": TEXT,
            "provenance": TEXT,
            "horizon_tick": POSITIVE,
            "end_tick": POSITIVE,
            "actors": array_schema("actor"),
            "roles": object_schema({"picker_id": TEXT, "packer_id": TEXT, "shipper_id": TEXT}),
            "cart": {"$ref": "#/$defs/cart"},
            "station": object_schema(
                {"station_id": TEXT, "bench_owner": TEXT, "empty_owner": TEXT}
            ),
            "port_id": TEXT,
            "owners": array_schema("owner"),
            "recipes": array_schema("recipe"),
            "materials": array_schema("material"),
            "pool_owners": object_schema({"carrier": TEXT, "package": TEXT, "shipped": TEXT}),
            "times": object_schema({key: POSITIVE for key in TIME_FIELDS}),
            "orders": array_schema("order"),
            "path_clearance_m": RATIONAL,
        }
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_ID,
        "$defs": _definitions(),
        **result,
    }


@cache
def _validator() -> Draft202012Validator:
    schema = profile_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _exact_json(value: Any) -> None:
    if isinstance(value, (bool, float)):
        raise ValueError("Profile quantities/clocks must use exact integer rational fields")
    if isinstance(value, dict):
        for item in value.values():
            _exact_json(item)
    elif isinstance(value, list):
        for item in value:
            _exact_json(item)


def validate_document(document: Any) -> None:
    canonical_bytes(document)  # Reject cycles, unsupported values and non-string keys first.
    _exact_json(document)
    try:
        _validator().validate(document)
    except ValidationError as exc:
        path = "/".join(map(str, exc.absolute_path))
        raise ValueError(f"Invalid light profile at {path}: {exc.message}") from exc
