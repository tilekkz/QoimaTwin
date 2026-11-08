"""Strict proposed trace and checkpoint envelopes, independent of frontend wire contracts."""

from functools import cache

from jsonschema import Draft202012Validator, ValidationError

from app.v3.flow_run_schema_state import state_defs
from app.v3.interface import Json
from app.v3.run_schema import HASH, STRING, TICK, array, nullable, obj, ref

SCHEMA_ID = "qoima.connected-small-run.v3-proposal"
MAX_CHUNK_BYTES = 8 * 1024 * 1024


def capability_schema() -> Json:
    return obj(
        {
            k: {"const": v}
            for k, v in {
                "actual_engine_component_run": True,
                "internal_inventory_integration": True,
                "full_v3": False,
                "frontend_adapter": False,
                "hand_contact_proof": False,
                "arbitrary_seek": False,
                "interpolation": False,
                "captured_checkpoint_retrieval": True,
            }.items()
        }
    )


def checkpoint_schema() -> Json:
    return obj(
        {
            "tick": TICK,
            "last_seq": {"type": "integer", "minimum": -1},
            "state_hash": HASH,
            "state": ref("state"),
        }
    )


def event_schema() -> Json:
    belt = obj(
        {
            "seq": TICK,
            "tick": TICK,
            "kind": STRING,
            "job_id": STRING,
            "hu_id": STRING,
            "payload_id": STRING,
            "edge_id": nullable(STRING),
            "pose": nullable(ref("pose")),
            "planned_end_tick": nullable(TICK),
            "resources": array(STRING),
        }
    )
    return obj(
        {
            "seq": TICK,
            "tick": TICK,
            "kind": STRING,
            "order_id": STRING,
            "actor_id": nullable(STRING),
            "operation": nullable(ref("operation")),
            "delta": nullable(ref("delta")),
            "belt_event": nullable(belt),
        }
    )


def catalog_schema() -> Json:
    identity = obj({"container_id": STRING, "recipe_id": STRING})
    return obj(
        {
            "graph": obj(
                {"graph_id": STRING, "node_ids": array(STRING), "arcs": array({"type": "object"})}
            ),
            "source_revision": nullable(STRING),
            "source_hashes": array({**array(STRING), "minItems": 2, "maxItems": 2}),
            "actors": array({"type": "object", "required": ["actor_id"]}),
            "owners": array({"type": "object", "required": ["owner_id"]}),
            "container_recipes": array({"type": "object", "required": ["recipe_id"]}),
            "containers": array(identity),
            "units": array({"type": "object", "required": ["unit_id"]}),
        }
    )


def metrics_schema() -> Json:
    window = {"type": "object", "properties": {"tick": TICK}, "required": ["tick"]}
    return obj(
        {
            "metrics_version": {"const": "qoima-light-flow-metrics-v1"},
            "counts_boundary": {"const": "settled_tick_inclusive"},
            "integral_window": {"const": "[0,T)"},
            "cycle_completion": {"const": "outbound_business_handover"},
            "role_basis": {"const": "fixed_source_roster"},
            "backlog_at_horizon": TICK,
            "at_horizon": window,
            "at_end": window,
        }
    )


def schema() -> Json:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": state_defs(),
        **obj(
            {
                "schema_id": {"const": SCHEMA_ID},
                "schema_version": {"const": "0.1.0"},
                "contract_status": {"const": "proposal"},
                "run_id": HASH,
                "input_hash": HASH,
                "engine_version": STRING,
                "source_revision": nullable(STRING),
                "horizon_tick": TICK,
                "end_tick_limit": TICK,
                "observed_until_tick": TICK,
                "status": {"enum": ["complete", "partial"]},
                "capabilities": capability_schema(),
                "catalog": catalog_schema(),
                "metrics": metrics_schema(),
                "events": array(event_schema()),
                "checkpoints": array(checkpoint_schema()),
                "at_horizon": checkpoint_schema(),
                "at_end": checkpoint_schema(),
            }
        ),
    }


@cache
def validator(kind: str = "run") -> Draft202012Validator:
    value = schema()
    if kind in {"events", "checkpoints"}:
        value = {"$defs": state_defs(), **obj({"items": value["properties"][kind]})}
    elif kind == "metadata":
        value = {
            "$defs": state_defs(),
            **obj(
                {
                    k: v
                    for k, v in value["properties"].items()
                    if k not in {"events", "checkpoints", "catalog"}
                }
            ),
        }
    Draft202012Validator.check_schema(value)
    return Draft202012Validator(value)


def validate_schema(value: Json, kind: str = "run") -> None:
    try:
        validator(kind).validate(value)
    except ValidationError as exc:
        raise ValueError(f"connected flow {kind} schema: {exc.json_path}: {exc.message}") from exc
