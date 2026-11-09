"""Explicit immutable input projection; graph private adjacency and history are excluded."""

from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from fractions import Fraction
from typing import Any

from app.v3.input_models import ImmutableDocument, V3Bundle
from app.v3.light_flow_models import FlowProfile
from app.v3.stock_ledger import StockLedger


def record(value: Any) -> Any:
    if isinstance(value, Fraction):
        return {"numerator": value.numerator, "denominator": value.denominator}
    if isinstance(value, ImmutableDocument):
        return value.decode()
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: record(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Mapping):
        return {key: record(item) for key, item in value.items()}
    if isinstance(value, (frozenset, set)):
        return [record(item) for item in sorted(value)]
    if isinstance(value, (tuple, list)):
        return [record(item) for item in value]
    if value is None or type(value) in (str, int, float, bool):
        return value
    raise ValueError("Unsupported immutable input projection")


def normalized_choices(document: dict[str, Any]) -> dict[str, Any]:
    def normalize(value: Any) -> Any:
        if isinstance(value, dict):
            if set(value) == {"numerator", "denominator"}:
                return record(Fraction(value["numerator"], value["denominator"]))
            return {key: normalize(child) for key, child in value.items()}
        if isinstance(value, list):
            return [normalize(child) for child in value]
        return value

    result: dict[str, Any] = normalize(document)
    for key, identity in (
        ("actors", "actor_id"),
        ("owners", "owner_id"),
        ("materials", "container_id"),
        ("recipes", "recipe_id"),
        ("orders", "order_id"),
    ):
        result[key].sort(key=lambda row: row[identity])
    for recipe in result["recipes"]:
        recipe["allowed_archetypes"].sort()
    return result


def source_record(bundle: V3Bundle) -> dict[str, Any]:
    return {item.name: record(getattr(bundle, item.name)) for item in fields(bundle)}


def materialized_record(profile: FlowProfile, ledger: StockLedger) -> dict[str, Any]:
    derived = {
        item.name: record(getattr(profile, item.name))
        for item in fields(profile)
        if item.name not in {"graph", "stock"}
    }
    return {
        "profile": derived,
        "graph": {
            "graph_id": profile.graph.graph_id,
            "node_ids": list(profile.graph.node_ids),
            "arcs": record(profile.graph.arcs),
        },
        "initial_state": {
            "stock": record(ledger.snapshot()),
            "balance": record(ledger.balance()),
            "source_units": record(profile.stock.units),
            "source_owners": record(profile.stock.owners),
        },
    }
