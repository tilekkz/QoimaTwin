"""Whole namespace binds outer and original physical input hashes independently."""

from functools import cache

from jsonschema import Draft202012Validator, ValidationError

from app.v3.flow_transport_schema import manifest_schema
from app.v3.flow_transport_schema import validate_manifest as validate_ranges
from app.v3.interface import Json
from app.v3.run_schema import HASH

MANIFEST_ID = "qoima.connected-manual-whole-manifest.v3-proposal"


def schema() -> Json:
    value = manifest_schema()
    value["properties"]["schema_id"] = {"const": MANIFEST_ID}
    value["properties"]["physical_input_hash"] = HASH
    value["required"] = list(value["properties"])
    return value


@cache
def validator() -> Draft202012Validator:
    value = schema()
    Draft202012Validator.check_schema(value)
    return Draft202012Validator(value)


def validate_manifest(value: Json) -> None:
    try:
        validator().validate(value)
    except ValidationError as exc:
        raise ValueError(f"whole manifest schema: {exc.json_path}: {exc.message}") from exc
    legacy_shape = {k: v for k, v in value.items() if k != "physical_input_hash"}
    legacy_shape["schema_id"] = "qoima.connected-small-manifest.v3-proposal"
    validate_ranges(legacy_shape)
    for key in ("horizon_tick", "observed_until_tick", "chunk_ticks", "max_chunk_bytes"):
        if type(value[key]) is not int:
            raise ValueError("Whole transport clocks/bounds require exact integers")
    rows = [value[k] for k in ("inputs", "catalog", "metadata")]
    for row in [*rows, *value["event_chunks"], *value["checkpoint_chunks"]]:
        if any(
            type(number) is not int for key, number in row.items() if key not in {"path", "sha256"}
        ):
            raise ValueError("Whole raw descriptors require exact integer bounds")
