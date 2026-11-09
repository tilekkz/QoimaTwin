"""Strict raw-byte manifest and chunk schemas for the manual execution proposal."""

from functools import lru_cache

from jsonschema import Draft202012Validator, ValidationError

from app.v3.interface import Json
from app.v3.run_schema import HASH, STRING, TICK, array, obj, schema

MAX_CHUNK_BYTES = 8 * 1024 * 1024


def manifest_schema() -> Json:
    descriptor = {"path": STRING, "bytes": TICK, "sha256": HASH}
    chunk = obj(
        {
            **descriptor,
            **{key: TICK for key in ("start_tick", "end_tick", "first_tick", "last_tick")},
        }
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:qoima:manual-manifest:v3-proposal:0.1.0",
        **obj(
            {
                "schema_id": {"const": "qoima.manual-manifest.v3-proposal"},
                "schema_version": {"const": "0.1.0"},
                "contract_status": {"const": "proposal"},
                "run_id": HASH,
                "clock": schema()["properties"]["clock"],
                "observed_until_tick": TICK,
                "max_chunk_bytes": {"type": "integer", "minimum": 13, "maximum": MAX_CHUNK_BYTES},
                "chunk_ticks": {"type": "integer", "minimum": 1},
                "metadata": obj(descriptor),
                "graph_document": obj(descriptor),
                "event_chunks": array(chunk),
                "snapshot_chunks": {**array(chunk), "minItems": 1},
            }
        ),
    }


@lru_cache(maxsize=4)
def _validator(kind: str) -> Draft202012Validator:
    value = schema()
    if kind == "manifest":
        value = manifest_schema()
    elif kind == "metadata":
        properties = {
            key: item
            for key, item in value["properties"].items()
            if key not in {"events", "snapshots", "graph_document"}
        }
        value = {"$defs": value["$defs"], **obj(properties)}
    else:
        item = value["properties"][kind]["items"]
        value = {"$defs": value["$defs"], **obj({"items": array(item)})}
    Draft202012Validator.check_schema(value)
    return Draft202012Validator(value)


def validate_transport(value: Json, kind: str) -> None:
    try:
        _validator(kind).validate(value)
    except ValidationError as exc:
        raise ValueError(f"manual {kind} schema: {exc.json_path}: {exc.message}") from exc
    if kind != "manifest":
        return
    for name in ("event_chunks", "snapshot_chunks"):
        previous = -1
        for row in value[name]:
            start, end = row["start_tick"], row["end_tick"]
            if start % value["chunk_ticks"] or end - start != value["chunk_ticks"]:
                raise ValueError("manual chunk uses an inconsistent half-open window")
            if not start <= row["first_tick"] <= row["last_tick"] < end:
                raise ValueError("manual chunk item range exceeds its declared window")
            if row["first_tick"] < previous or row["last_tick"] > value["observed_until_tick"]:
                raise ValueError("manual chunks are unordered or exceed observed time")
            if row["bytes"] > value["max_chunk_bytes"]:
                raise ValueError("manual chunk descriptor exceeds its raw byte bound")
            previous = row["last_tick"]
