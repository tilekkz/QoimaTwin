"""Immutable input/catalog identity binding checked again when opening an artifact."""

from typing import Any

from app.storage.canonical_json import canonical_bytes, parse_json


def catalog_from_inputs(raw: bytes) -> dict[str, Any]:
    frozen = parse_json(raw)
    if not isinstance(frozen, dict):
        raise ValueError("Frozen inputs require an object")
    profile, initial = frozen["profile"], frozen["initial_state"]
    containers = initial["stock"]["containers"]
    recipes = {c["recipe"]["recipe_id"]: c["recipe"] for c in containers}
    return {
        "graph": frozen["graph"],
        "source_revision": profile["source_revision"],
        "source_hashes": profile["source_hashes"],
        "actors": profile["actors"],
        "owners": [*initial["source_owners"], *profile["owners"]],
        "container_recipes": [recipes[k] for k in sorted(recipes)],
        "containers": [
            {"container_id": c["container_id"], "recipe_id": c["recipe"]["recipe_id"]}
            for c in sorted(containers, key=lambda c: c["container_id"])
        ],
        "units": initial["source_units"],
    }


def validate_input_binding(run: dict[str, Any], raw: bytes) -> None:
    frozen = parse_json(raw)
    if not isinstance(frozen, dict) or canonical_bytes(frozen) != raw:
        raise ValueError("Frozen inputs must be canonical JSON")
    if canonical_bytes(run["catalog"]) != canonical_bytes(catalog_from_inputs(raw)):
        raise ValueError("Immutable catalog/source differs from frozen input evidence")
    choices = frozen["choices"]
    expected = {"horizon_tick": run["horizon_tick"], "end_tick": run["end_tick_limit"]}
    if canonical_bytes({k: choices[k] for k in expected}) != canonical_bytes(expected):
        raise ValueError("Run clock differs from frozen choices")
