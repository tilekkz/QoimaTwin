"""Separate immutable physical recipes/ancestry from captured mutable state."""

from dataclasses import fields
from typing import Any

from app.storage.canonical_json import sha256_hex
from app.v3.flow_profile_wire import record
from app.v3.light_flow_models import FlowEvent, FlowProfile, FlowSnapshot
from app.v3.stock_models import Container, ContainerContents, StockDelta


def container(value: Container) -> dict[str, Any]:
    return {
        "container_id": value.container_id,
        "owner_id": value.owner_id,
        "sealed_for": value.sealed_for,
    }


def contents(value: ContainerContents) -> dict[str, Any]:
    return {
        "container": container(value.container),
        "gross_mass_kg": record(value.gross_mass_kg),
        "units": [
            {"unit_id": u.token.unit_id, "position": record(u.position)} for u in value.units
        ],
    }


def delta(value: StockDelta) -> dict[str, Any]:
    return {
        "transaction_id": value.transaction_id,
        "revision": value.revision,
        "operation": value.operation,
        "unit_ids": list(value.unit_ids),
        "before": [contents(c) for c in value.before],
        "after": [contents(c) for c in value.after],
    }


def event(value: FlowEvent) -> dict[str, Any]:
    result = {f.name: record(getattr(value, f.name)) for f in fields(value) if f.name != "delta"}
    result["delta"] = delta(value.delta) if value.delta else None
    return result


def checkpoint(value: FlowSnapshot) -> dict[str, Any]:
    state = {
        f.name: record(getattr(value, f.name))
        for f in fields(value)
        if f.name not in {"stock", "last_seq", "tick"}
    }
    state["stock"] = {
        "revision": value.stock.revision,
        "containers": [container(c) for c in value.stock.containers],
        "locations": record(value.stock.locations),
    }
    return {
        "tick": value.tick,
        "last_seq": value.last_seq,
        "state_hash": sha256_hex(state),
        "state": state,
    }


def catalog(profile: FlowProfile, graph: dict[str, Any]) -> dict[str, Any]:
    containers = (*profile.stock.containers, *profile.materials)
    recipes = {c.recipe.recipe_id: record(c.recipe) for c in containers}
    return {
        "graph": graph,
        "source_revision": profile.source_revision,
        "source_hashes": record(profile.source_hashes),
        "actors": record(profile.actors),
        "owners": record((*profile.stock.owners, *profile.owners)),
        "container_recipes": [recipes[k] for k in sorted(recipes)],
        "containers": [
            {"container_id": c.container_id, "recipe_id": c.recipe.recipe_id}
            for c in sorted(containers, key=lambda c: c.container_id)
        ],
        "units": record(profile.stock.units),
    }
