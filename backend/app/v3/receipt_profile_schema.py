"""Strict receipt profile choices extend the vocabulary without mutating the old schema."""

from copy import deepcopy
from functools import cache
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

from app.storage.canonical_json import canonical_bytes
from app.v3.flow_profile_schema import (
    POSITIVE,
    RATIONAL,
    TEXT,
    TICK,
    array_schema,
    object_schema,
    profile_schema,
)

SCHEMA_ID = "qoima.receipt-flow-profile.v3-proposal"
SCHEMA_VERSION = "0.1.0"


def _array(items: dict[str, Any], *, size: int | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {"type": "array", "items": items, "minItems": size or 1}
    if size is not None:
        value["maxItems"] = size
    return value


def _buffer_schema() -> dict[str, Any]:
    return object_schema(
        {
            "owner_id": TEXT,
            "port_id": TEXT,
            "zone_id": TEXT,
            "bounds_xz": _array(RATIONAL, size=4),
            "path_xz": {**_array(_array(RATIONAL, size=2)), "minItems": 2},
            "height_m": RATIONAL,
            "max_gross_kg": RATIONAL,
            "clearance_m": RATIONAL,
        }
    )


def _definitions() -> dict[str, Any]:
    return {
        "receipt_port": object_schema(
            {
                "port_id": TEXT,
                "buffer_owner_ids": {**_array(TEXT), "uniqueItems": True},
                "receiver_ids": {**_array({"enum": ["R01", "R02"]}), "uniqueItems": True},
            }
        ),
        "receipt_buffer": _buffer_schema(),
        "receipt": object_schema(
            {
                "receipt_id": TEXT,
                "hu_id": TEXT,
                "sku_id": TEXT,
                "lot_id": TEXT,
                "quantity_units": POSITIVE,
                "arrival_tick": TICK,
                "port_id": TEXT,
                "slot_id": TEXT,
            }
        ),
    }


def receipt_profile_schema() -> dict[str, Any]:
    result = deepcopy(profile_schema())
    result["$id"] = SCHEMA_ID
    result["properties"]["schema_id"] = {"const": SCHEMA_ID}
    result["properties"]["schema_version"] = {"const": SCHEMA_VERSION}
    result["$defs"]["owner"]["properties"]["kind"]["enum"].extend(["buffer", "worker"])
    result["$defs"].update(_definitions())
    additions = {
        "receipt_ports": array_schema("receipt_port"),
        "receipt_buffers": array_schema("receipt_buffer"),
        "receipts": array_schema("receipt"),
        "receipt_times": object_schema({"pickup": POSITIVE, "place": POSITIVE}),
    }
    result["properties"].update(additions)
    result["required"].extend(additions)
    return result


@cache
def _validator() -> Draft202012Validator:
    schema = receipt_profile_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _exact(value: Any) -> None:
    if isinstance(value, (bool, float)):
        raise ValueError("Receipt choices require exact integer rational quantities and clocks")
    if isinstance(value, dict):
        for item in value.values():
            _exact(item)
    elif isinstance(value, list):
        for item in value:
            _exact(item)


def validate_document(document: Any) -> None:
    canonical_bytes(document)
    _exact(document)
    try:
        _validator().validate(document)
    except ValidationError as exc:
        path = "/".join(map(str, exc.absolute_path))
        raise ValueError(f"Invalid receipt profile at {path}: {exc.message}") from exc
