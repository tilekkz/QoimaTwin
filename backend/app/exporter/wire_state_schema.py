"""Nested public-state schemas: all mutable fields have an explicit shape."""

from typing import Any

TEXT = {"type": "string", "minLength": 1}
COUNT = {"type": "integer", "minimum": 0}
BOOL = {"type": "boolean"}
VEC = {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3}
STATES = {"enum": ["IDLE", "TRAVEL", "BUSY_SERVICE", "BLOCKED", "WAIT_RESOURCE"]}


def obj(fields: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": fields,
        "required": list(fields),
        "additionalProperties": False,
    }


def array(item: dict[str, Any]) -> dict[str, Any]:
    return {"type": "array", "items": item}


def nullable(item: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [item, {"type": "null"}]}


def row(*items: dict[str, Any]) -> dict[str, Any]:
    return {"type": "array", "prefixItems": list(items), "items": False, "minItems": len(items)}


def cargo() -> dict[str, Any]:
    return obj(
        {"cargo_id": TEXT, "kind": {"enum": ["tote", "parcel"]}, "order_id": TEXT, "target": TEXT}
    )


def pallet() -> dict[str, Any]:
    return obj(
        {
            "pallet_id": TEXT,
            "state": {"enum": ["OPEN", "SEAL_PENDING", "SEALED", "CLAIMED", "DISPATCHED"]},
            "parcels": array(TEXT),
            "reserved": COUNT,
            "first_placement_tick": nullable(COUNT),
            "generation": COUNT,
            "expires_tick": nullable(COUNT),
        }
    )


def state_schema(action: dict[str, Any]) -> dict[str, Any]:
    return obj(
        {
            "actors": array(actor_schema(action)),
            "conveyor": conveyor_schema(),
            "ledger": ledger_schema(),
            "orders": orders_schema(),
            "totes": obj({"free": array(TEXT), "allocated": array(TEXT)}),
            "stations": array(station_schema()),
            "shipping": shipping_schema(),
            "receiving": receiving_schema(),
            "placements": {
                "type": "object",
                "additionalProperties": obj(
                    {
                        "container_id": nullable(TEXT),
                        "slot_index": nullable(COUNT),
                        "vehicle_id": nullable(TEXT),
                    }
                ),
            },
        }
    )


def actor_schema(action: dict[str, Any]) -> dict[str, Any]:
    return obj(
        {
            "actor_id": TEXT,
            "role": TEXT,
            "state": STATES,
            "pos": nullable(VEC),
            "action": nullable(action),
            "blocked_since_tick": nullable(COUNT),
            "carrying_cargo_id": nullable(TEXT),
        }
    )


def conveyor_schema() -> dict[str, Any]:
    return obj(
        {
            "cells": array(row(TEXT, TEXT)),
            "cargo": array(cargo()),
            "admissions": array(
                obj({"inlet": TEXT, "cargo_id": TEXT, "ready_tick": COUNT, "owner": TEXT})
            ),
            "merge_cursors": array(row(TEXT, COUNT)),
        }
    )


def ledger_schema() -> dict[str, Any]:
    return obj(
        {
            "balances": array(row(TEXT, TEXT, TEXT, TEXT, COUNT)),
            "reservations": array(row(TEXT, TEXT, TEXT, TEXT, COUNT)),
            "claims": array(row(TEXT, TEXT, TEXT, TEXT, TEXT, COUNT)),
            "accepted": array(row(TEXT, COUNT)),
        }
    )


def orders_schema() -> dict[str, Any]:
    return obj(
        {
            "queue": array(TEXT),
            "picking": array(obj({"order_id": TEXT, "actor_id": TEXT, "tote_id": TEXT})),
            "counts": obj(dict.fromkeys(["arrived", "rejected", "packed", "dispatched"], COUNT)),
            "status": {
                "type": "object",
                "additionalProperties": {
                    "enum": ["queued", "admitted", "packed", "dispatched", "unfulfilled_inventory"]
                },
            },
        }
    )


def station_schema() -> dict[str, Any]:
    return obj(
        {
            "pack_id": TEXT,
            "waiting": array(TEXT),
            "in_service": nullable(TEXT),
            "cargo": array(cargo()),
            "blocked_parcel": nullable(TEXT),
            "blocked_since": nullable(COUNT),
            "reserved_wip": COUNT,
        }
    )


def receiving_schema() -> dict[str, Any]:
    return obj(
        {
            "external": array(TEXT),
            "area": array(
                obj(
                    {
                        "pallet_id": TEXT,
                        "receipt_id": TEXT,
                        "state": {"enum": ["WAITING", "IN_SERVICE", "PROCESSED", "CLAIMED"]},
                    }
                )
            ),
            "forklift_busy": BOOL,
            "staging_used": COUNT,
            "counts": obj(dict.fromkeys(["accepted", "putaway"], COUNT)),
        }
    )


def shipping_schema() -> dict[str, Any]:
    return obj(
        {
            "buffer": array(TEXT),
            "open_pallet": nullable(pallet()),
            "sealed_queue": array(pallet()),
            "scanning": array(
                obj({"actor_id": TEXT, "order_id": nullable(TEXT), "until_tick": COUNT})
            ),
            "outbound": obj(
                {
                    "busy": BOOL,
                    "tasks": array(TEXT),
                    "carrying": nullable(
                        obj(
                            {
                                "pallet_id": TEXT,
                                "state": {"const": "CLAIMED"},
                                "parcels": array(TEXT),
                            }
                        )
                    ),
                }
            ),
        }
    )
