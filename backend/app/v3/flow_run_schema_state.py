"""Explicit mutable checkpoint and operation schemas; recipes are never state fields."""

from app.v3.interface import Json
from app.v3.run_schema import STRING, TICK, array, nullable, obj, ref


def motion_defs() -> Json:
    rational = obj(
        {"numerator": {"type": "integer"}, "denominator": {"type": "integer", "minimum": 1}}
    )
    route = obj(
        {
            "graph_id": STRING,
            "node_ids": array(STRING),
            "arc_ids": array(STRING),
            "length_m": rational,
            "cost_m": rational,
        }
    )
    operation = obj(
        {
            "kind": STRING,
            "order_id": STRING,
            "start_tick": TICK,
            "planned_end_tick": TICK,
            "source_node": STRING,
            "target_node": STRING,
            "route": nullable(route),
            "carrying_id": nullable(STRING),
            "cart_id": nullable(STRING),
        }
    )
    pose = obj({"edge_id": STRING, "progress": rational, "yaw_quarters": rational})
    return {
        "rational": rational,
        "operation": operation,
        "pose": pose,
        "vector": {**array(rational), "minItems": 3, "maxItems": 3},
        "motion": obj(
            {
                "phase": STRING,
                "start_tick": TICK,
                "planned_end_tick": TICK,
                "start": pose,
                "end": pose,
            }
        ),
    }


def stock_defs() -> Json:
    container = obj({"container_id": STRING, "owner_id": STRING, "sealed_for": nullable(STRING)})
    placement = obj({"unit_id": STRING, "position": nullable(ref("vector"))})
    contents = obj(
        {"container": container, "gross_mass_kg": ref("rational"), "units": array(placement)}
    )
    stock = obj(
        {
            "revision": TICK,
            "containers": array(container),
            "locations": array(obj({**placement["properties"], "container_id": STRING})),
        }
    )
    count = {"type": "array", "prefixItems": [STRING, TICK], "items": False, "minItems": 2}
    balance = obj(
        {
            **{
                k: array(count)
                for k in ("units_by_sku", "onsite_units_by_sku", "shipped_units_by_sku")
            },
            **{
                k: ref("rational")
                for k in (
                    "contents_mass_kg",
                    "primary_tare_kg",
                    "container_tare_kg",
                    "onsite_mass_kg",
                    "shipped_mass_kg",
                    "disposed_mass_kg",
                )
            },
        }
    )
    return {
        "stock": stock,
        "balance": balance,
        "delta": obj(
            {
                "transaction_id": STRING,
                "revision": TICK,
                "operation": STRING,
                "unit_ids": array(STRING),
                "before": array(contents),
                "after": array(contents),
            }
        ),
    }


def actor_defs() -> Json:
    worker = obj(
        {
            "actor_id": STRING,
            "node": nullable(STRING),
            "order_id": nullable(STRING),
            "operation": nullable(ref("operation")),
            "waiting_since": nullable(TICK),
            "queue_ticks": TICK,
            "paid_ticks": TICK,
        }
    )
    cart = obj(
        {
            "cart_id": STRING,
            "node": nullable(STRING),
            "operation": nullable(ref("operation")),
            "order_id": nullable(STRING),
        }
    )
    order = obj(
        {
            "order_id": STRING,
            "status": STRING,
            "admitted_tick": nullable(TICK),
            "shipped_tick": nullable(TICK),
        }
    )
    return {"worker": worker, "cart": cart, "order": order}


def state_defs() -> Json:
    lease = {**array(STRING), "minItems": 2, "maxItems": 2}
    carrier = obj(
        {
            "job_id": STRING,
            "hu_id": STRING,
            "payload_id": STRING,
            "status": STRING,
            "pose": nullable(ref("pose")),
            "motion": nullable(ref("motion")),
            "occupied_cells": array(STRING),
        }
    )
    belt = obj(
        {
            "tick": TICK,
            "arrived": TICK,
            "completed": TICK,
            "carriers": array(carrier),
            "leases": array(lease),
            "queue_ticks": TICK,
        }
    )
    state = obj(
        {
            "stock": ref("stock"),
            "balance": ref("balance"),
            "workers": array(ref("worker")),
            "cart": ref("cart"),
            "orders": array(ref("order")),
            "leases": array(lease),
            "belt": belt,
        }
    )
    return {**motion_defs(), **stock_defs(), **actor_defs(), "state": state}
