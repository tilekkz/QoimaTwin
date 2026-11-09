"""Separate native whole-HU envelope; legacy receipt schema remains unchanged."""

from functools import cache

from jsonschema import Draft202012Validator, ValidationError

from app.v3.interface import Json
from app.v3.receipt_run_schema import schema as receipt_schema
from app.v3.run_schema import HASH, STRING, TICK, array, nullable, obj

SCHEMA_ID = "qoima.connected-manual-whole-run.v3-proposal"
PUBLICATION_VERSION = "qoima-whole-publication-0.1.0"


def _extend(value: Json, fields: Json) -> None:
    value["properties"].update(fields)
    value["required"] = list(value["properties"])


def whole_view() -> Json:
    ticks = (
        "admitted",
        "picked",
        "buffered",
        "buffer_picked",
        "port_reserved",
        "service_started",
        "shipped",
        "returned",
    )
    return obj(
        {
            "job_id": STRING,
            "status": {
                "enum": [
                    "unreleased",
                    "waiting",
                    "approaching",
                    "carrying",
                    "buffered",
                    "service",
                    "returning",
                    "complete",
                ]
            },
            "actor_id": nullable(STRING),
            "buffer_owner_id": nullable(STRING),
            **{key + "_tick": nullable(TICK) for key in ticks},
            "wait_reason": {
                "enum": [
                    None,
                    "buffer_busy",
                    "shipper_busy",
                    "port_busy",
                    "shipped_capacity",
                    "service_window",
                ]
            },
            "paid_exposure_ticks": TICK,
            "port_reservation_ticks": TICK,
            "port_service_ticks": TICK,
        }
    )


def schema() -> Json:
    result = receipt_schema()
    props, defs = result["properties"], result["$defs"]
    props["schema_id"] = {"const": SCHEMA_ID}
    props["publication_version"] = {"const": PUBLICATION_VERSION}
    props.pop("receipt_metrics")
    props["metrics"] = obj(
        {
            "metrics_version": {"const": "qoima-whole-flow-metrics-v1"},
            "counts_boundary": {"const": "settled_tick_inclusive"},
            "integral_window": {"const": "[0,T)"},
            "at_horizon": {"type": "object"},
            "at_end": {"type": "object"},
        }
    )
    _extend(result, {"physical_input_hash": HASH})
    _extend(props["capabilities"], {"manual_whole_hu": {"const": True}})
    _extend(defs["state"], {"whole_orders": array(whole_view())})
    _extend(props["events"]["items"], {"whole_order": nullable(whole_view())})
    _extend(
        props["catalog"],
        {"whole_process": {"type": "object"}, "workflow_profile": {"type": "object"}},
    )
    return result


@cache
def validator(kind: str = "run") -> Draft202012Validator:
    result = schema()
    props = result["properties"]
    if kind in {"events", "checkpoints"}:
        result = {"$defs": result["$defs"], **obj({"items": props[kind]})}
    elif kind == "metadata":
        result = {
            "$defs": result["$defs"],
            **obj(
                {k: v for k, v in props.items() if k not in {"catalog", "events", "checkpoints"}}
            ),
        }
    Draft202012Validator.check_schema(result)
    return Draft202012Validator(result)


def validate_schema(value: Json, kind: str = "run") -> None:
    try:
        validator(kind).validate(value)
    except ValidationError as exc:
        raise ValueError(f"whole {kind} schema: {exc.json_path}: {exc.message}") from exc
