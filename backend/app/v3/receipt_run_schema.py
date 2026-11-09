"""Strict receipt publication envelopes extend captured state without granting future stock."""

from functools import cache

from jsonschema import Draft202012Validator, ValidationError

from app.v3.flow_run_schema import schema as light_schema
from app.v3.interface import Json
from app.v3.run_schema import STRING, TICK, array, nullable, obj, ref

SCHEMA_ID = "qoima.connected-receipt-small-run.v3-proposal"
PUBLICATION_VERSION = "qoima-receipt-publication-0.1.0"


def definition() -> Json:
    return obj(
        {
            **{k: STRING for k in ("receipt_id", "hu_id", "sku_id", "lot_id")},
            "quantity_units": {"type": "integer", "minimum": 1},
        }
    )


def token() -> Json:
    recipe = obj(
        {
            "archetype_id": STRING,
            "dimensions": ref("vector"),
            "contents_mass_kg": ref("rational"),
            "primary_tare_kg": ref("rational"),
        }
    )
    return obj(
        {
            **{k: STRING for k in ("unit_id", "origin_hu", "sku_id", "lot_id")},
            "ordinal": {"type": "integer", "minimum": 1},
            "recipe": recipe,
        }
    )


def claim() -> Json:
    return obj(
        {
            **{k: STRING for k in ("claim_id", "job_id", "container_id")},
            "unit_ids": {**array(STRING), "minItems": 1},
            "whole_hu": {"type": "boolean"},
        }
    )


def receipt_view() -> Json:
    return obj(
        {
            "receipt_id": STRING,
            "status": {
                "enum": [
                    "unreleased",
                    "waiting",
                    "approaching",
                    "awaiting_service",
                    "service",
                    "carrying",
                    "buffered",
                    "returning",
                    "complete",
                ]
            },
            "actor_id": nullable(STRING),
            "buffer_owner_id": nullable(STRING),
            **{
                k: nullable(TICK)
                for k in ("admitted_tick", "credited_tick", "placed_tick", "returned_tick")
            },
            "wait_reason": {
                "enum": [
                    None,
                    "slot_busy",
                    "buffer_busy",
                    "receiver_busy",
                    "service_window",
                    "port_busy",
                ]
            },
            "paid_exposure_ticks": TICK,
        }
    )


def _extend(value: Json, extras: Json) -> None:
    value["properties"].update(extras)
    value["required"] = list(value["properties"])


def schema() -> Json:
    value = light_schema()
    props, defs = value["properties"], value["$defs"]
    props["schema_id"] = {"const": SCHEMA_ID}
    _extend(
        value,
        {
            "publication_version": {"const": PUBLICATION_VERSION},
            "receipt_metrics": obj({"at_horizon": counts(), "at_end": counts()}),
        },
    )
    _extend(
        props["capabilities"],
        {"receipt_inventory_creation": {"const": True}, "inventory_claims": {"const": True}},
    )
    _extend(
        defs["delta"],
        {
            "delta_type": {"enum": ["stock", "receipt_creation"]},
            "receipt": nullable(definition()),
            "created_tokens": array(token()),
        },
    )
    _extend(
        defs["state"],
        {
            "receipts": array(receipt_view()),
            "inventory": obj(
                {
                    "registered_receipt_ids": array(STRING),
                    "claims": array(claim()),
                    "claim_generation": TICK,
                }
            ),
        },
    )
    _extend(
        props["events"]["items"],
        {
            "receipt": nullable(receipt_view()),
            "inventory_claim": nullable(claim()),
            "released_claim_id": nullable(STRING),
            "resource_id": nullable(STRING),
        },
    )
    props["catalog"] = catalog_schema(props["catalog"])
    return value


def counts() -> Json:
    return obj(
        {
            key: TICK
            for key in (
                "tick",
                "arrived_receipts",
                "credited_receipts",
                "credited_units",
                "putaway_receipts",
                "returned_receipts",
                "pending_putaway",
                "pending_return",
                "receiver_resource_ticks",
            )
        }
    )


def catalog_schema(value: Json) -> Json:
    properties = value["properties"]
    properties.pop("containers")
    properties.pop("units")
    container = obj(
        {
            "container_id": STRING,
            "recipe_id": STRING,
            "initial_owner_id": STRING,
            "initial_sealed_for": nullable(STRING),
        }
    )
    offer = obj(
        {
            "definition": definition(),
            "arrival_tick": TICK,
            "port_id": STRING,
            "slot_owner_id": STRING,
            "container_recipe_id": STRING,
            "units": array(token()),
            "existence": {"const": "declared_until_service_completion"},
        }
    )
    process = obj(
        {
            "ports": array({"type": "object"}),
            "places": array({"type": "object"}),
            "offers": array({"type": "object"}),
            "pickup_tick": TICK,
            "place_tick": TICK,
            "route_policy": STRING,
        }
    )
    _extend(
        value,
        {
            "initial_containers": array(container),
            "initial_units": array(token()),
            "declared_receipts": array(offer),
            "orders": array({"type": "object"}),
            "receipt_process": process,
        },
    )
    return value


@cache
def validator(kind: str = "run") -> Draft202012Validator:
    value = schema()
    if kind in {"events", "checkpoints"}:
        value = {"$defs": value["$defs"], **obj({"items": value["properties"][kind]})}
    elif kind == "metadata":
        value = {
            "$defs": value["$defs"],
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
        raise ValueError(f"receipt {kind} schema: {exc.json_path}: {exc.message}") from exc
