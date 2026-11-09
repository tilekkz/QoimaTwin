"""Rebuild immutable receipt catalog from frozen input facts, independently of the run."""

from hashlib import sha256

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.flow_transport_inputs import catalog_from_inputs as light_catalog
from app.v3.interface import Json
from app.v3.receipt_run_inputs import verify_source
from app.v3.receipt_run_journal import same


def catalog_from_inputs(raw: bytes) -> Json:
    frozen = parse_json(raw)
    if not isinstance(frozen, dict):
        raise ValueError("Receipt frozen inputs require an object")
    result = light_catalog(raw)
    result["initial_units"] = result.pop("units")
    result.pop("containers")
    containers = frozen["initial_state"]["stock"]["containers"]
    result["initial_containers"] = [
        {
            "container_id": c["container_id"],
            "recipe_id": c["recipe"]["recipe_id"],
            "initial_owner_id": c["owner_id"],
            "initial_sealed_for": c["sealed_for"],
        }
        for c in sorted(containers, key=lambda c: c["container_id"])
    ]
    result["orders"] = frozen["profile"]["orders"]
    result["receipt_process"] = frozen["receipt_process"]
    result["declared_receipts"] = [
        _offer(r, result, containers)
        for r in sorted(
            frozen["receipt_process"]["offers"], key=lambda r: r["definition"]["receipt_id"]
        )
    ]
    return result


def _offer(offer: Json, catalog: Json, containers: list[Json]) -> Json:
    definition = offer["definition"]
    known = [u for u in catalog["initial_units"] if u["sku_id"] == definition["sku_id"]]
    if not known or type(definition["quantity_units"]) is not int:
        raise ValueError("Future receipt requires a known source recipe and exact quantity")
    wrappers = {c["container_id"]: c for c in containers}
    recipes = {canonical_bytes(u["recipe"]) for u in known}
    wrapper_recipes = {canonical_bytes(wrappers[u["origin_hu"]]["recipe"]) for u in known}
    if len(recipes) != 1 or len(wrapper_recipes) != 1:
        raise ValueError("Receipt source recipe is ambiguous")
    return {
        **offer,
        "container_recipe_id": wrappers[known[0]["origin_hu"]]["recipe"]["recipe_id"],
        "existence": "declared_until_service_completion",
        "units": [
            {
                "unit_id": f"{definition['hu_id']}:unit:{i:04d}",
                "origin_hu": definition["hu_id"],
                "sku_id": definition["sku_id"],
                "lot_id": definition["lot_id"],
                "ordinal": i,
                "recipe": known[0]["recipe"],
            }
            for i in range(1, definition["quantity_units"] + 1)
        ],
    }


def validate_input_binding(run: Json, raw: bytes) -> None:
    value = parse_json(raw)
    if not isinstance(value, dict) or canonical_bytes(value) != raw:
        raise ValueError("Receipt frozen inputs must be canonical JSON")
    if sha256(raw).hexdigest() != run["input_hash"]:
        raise ValueError("Receipt frozen input hash differs from native run")
    verify_source(value)
    same(run["catalog"], catalog_from_inputs(raw), "Receipt catalog differs from frozen inputs")
    same(
        {k: value["choices"][k] for k in ("horizon_tick", "end_tick")},
        {"horizon_tick": run["horizon_tick"], "end_tick": run["end_tick_limit"]},
        "Receipt run clock differs from frozen choices",
    )
