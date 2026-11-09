"""Receipt namespace with identical raw-file and half-open chunk transport constraints."""

from functools import cache

from jsonschema import Draft202012Validator, ValidationError

from app.v3.flow_transport_schema import manifest_schema as light_manifest_schema
from app.v3.flow_transport_schema import validate_manifest as validate_ranges
from app.v3.interface import Json

MANIFEST_ID = "qoima.connected-receipt-small-manifest.v3-proposal"


@cache
def validator() -> Draft202012Validator:
    schema = light_manifest_schema()
    schema["properties"]["schema_id"] = {"const": MANIFEST_ID}
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_manifest(value: Json) -> None:
    try:
        validator().validate(value)
    except ValidationError as exc:
        raise ValueError(f"receipt manifest schema: {exc.json_path}: {exc.message}") from exc
    validate_ranges({**value, "schema_id": "qoima.connected-small-manifest.v3-proposal"})
    for key in ("horizon_tick", "observed_until_tick", "chunk_ticks", "max_chunk_bytes"):
        if type(value[key]) is not int:
            raise ValueError("Receipt transport clocks and bounds require exact integers")
    descriptors = [value[k] for k in ("inputs", "catalog", "metadata")]
    descriptors += value["event_chunks"] + value["checkpoint_chunks"]
    for row in descriptors:
        for key, number in row.items():
            if key not in {"path", "sha256"} and type(number) is not int:
                raise ValueError("Receipt raw descriptor bounds require exact integers")
