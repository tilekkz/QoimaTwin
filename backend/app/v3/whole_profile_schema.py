"""Public whole choices extend the receipt vocabulary without changing old schemas."""

from functools import cache
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

from app.storage.canonical_json import canonical_bytes
from app.v3.flow_profile_schema import POSITIVE, TEXT, TICK, array_schema, object_schema
from app.v3.receipt_profile_schema import _exact, receipt_profile_schema

SCHEMA_ID = "qoima.whole-flow-profile.v3-proposal"
SCHEMA_VERSION = "0.1.0"


def whole_profile_schema() -> dict[str, Any]:
    result = receipt_profile_schema()
    result["$id"] = SCHEMA_ID
    result["properties"]["schema_id"] = {"const": SCHEMA_ID}
    result["properties"]["schema_version"] = {"const": SCHEMA_VERSION}
    result["$defs"].update(
        whole_order=object_schema(
            {"job_id": TEXT, "arrival_tick": TICK, "hu_id": TEXT, "port_id": TEXT}
        ),
        whole_port=object_schema(
            {
                "port_id": TEXT,
                "buffer_owner_ids": _ids(TEXT),
                "shipper_ids": _ids({"enum": ["S01", "S02"]}),
                "shipped_owner": TEXT,
            }
        ),
    )
    additions = {
        "whole_orders": array_schema("whole_order"),
        "whole_ports": array_schema("whole_port"),
        "whole_buffers": array_schema("receipt_buffer"),
        "whole_times": object_schema({"pickup": POSITIVE, "place": POSITIVE}),
    }
    result["properties"].update(additions)
    result["required"].extend(additions)
    return result


def _ids(items: dict[str, Any]) -> dict[str, Any]:
    return {"type": "array", "items": items, "minItems": 1, "uniqueItems": True}


@cache
def _validator() -> Draft202012Validator:
    schema = whole_profile_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_document(document: Any) -> None:
    canonical_bytes(document)
    _exact(document)
    try:
        _validator().validate(document)
    except ValidationError as exc:
        path = "/".join(map(str, exc.absolute_path))
        raise ValueError(f"Invalid whole profile at {path}: {exc.message}") from exc
