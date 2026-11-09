"""Strict raw-file descriptors and half-open connected-flow bundle boundaries."""

from functools import cache

from jsonschema import Draft202012Validator, ValidationError

from app.v3.flow_run_schema import MAX_CHUNK_BYTES
from app.v3.interface import Json
from app.v3.run_schema import HASH, TICK, array, obj


def manifest_schema() -> Json:
    descriptor = {
        "path": {"type": "string", "pattern": "^[a-z][a-z0-9_/.-]*\\.json$"},
        "bytes": TICK,
        "sha256": HASH,
    }
    chunk = obj(
        {**descriptor, **{k: TICK for k in ("start_tick", "end_tick", "first_tick", "last_tick")}}
    )
    return obj(
        {
            "schema_id": {"const": "qoima.connected-small-manifest.v3-proposal"},
            "schema_version": {"const": "0.1.0"},
            "contract_status": {"const": "proposal"},
            "run_id": HASH,
            "input_hash": HASH,
            "horizon_tick": TICK,
            "observed_until_tick": TICK,
            "chunk_ticks": {"const": 60_000_000},
            "max_chunk_bytes": {"type": "integer", "minimum": 13, "maximum": MAX_CHUNK_BYTES},
            "inputs": obj(descriptor),
            "catalog": obj(descriptor),
            "metadata": obj(descriptor),
            "event_chunks": array(chunk),
            "checkpoint_chunks": {**array(chunk), "minItems": 1},
        }
    )


@cache
def _validator() -> Draft202012Validator:
    schema = manifest_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_manifest(value: Json) -> None:
    try:
        _validator().validate(value)
    except ValidationError as exc:
        raise ValueError(f"flow manifest schema: {exc.json_path}: {exc.message}") from exc
    if value["inputs"]["sha256"] != value["input_hash"]:
        raise ValueError("Manifest input identity differs from raw input descriptor")
    descriptors = [value[k] for k in ("inputs", "catalog", "metadata")]
    for key in ("event_chunks", "checkpoint_chunks"):
        previous = -1
        limit = value["observed_until_tick"]
        if key == "checkpoint_chunks":
            limit = max(limit, value["horizon_tick"])
        for row in value[key]:
            start, end = row["start_tick"], row["end_tick"]
            if start % 60_000_000 or end - start != 60_000_000:
                raise ValueError("Chunk is not a 60-second half-open bucket")
            if not start <= row["first_tick"] <= row["last_tick"] < end:
                raise ValueError("Chunk content range escapes its half-open bucket")
            if row["first_tick"] < previous or row["last_tick"] > limit:
                raise ValueError("Chunk order or observed bound mismatch")
            if row["bytes"] > value["max_chunk_bytes"]:
                raise ValueError("Raw chunk descriptor exceeds configured bound")
            previous = row["last_tick"]
        descriptors.extend(value[key])
    paths = [d["path"] for d in descriptors]
    if len(paths) != len(set(paths)) or any(".." in p.split("/") for p in paths):
        raise ValueError("Descriptor paths must be unique relative artifact paths")
