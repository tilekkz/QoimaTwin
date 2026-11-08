"""Keep future descriptors immutable and current credited inventory separate."""

from dataclasses import fields

from app.storage.canonical_json import canonical_bytes, sha256_hex
from app.v3.flow_profile_wire import record
from app.v3.flow_run_values import catalog as light_catalog
from app.v3.flow_run_values import checkpoint as light_checkpoint
from app.v3.flow_run_values import delta as stock_delta
from app.v3.interface import Json
from app.v3.light_flow_models import FlowEvent, FlowSnapshot
from app.v3.receipt_flow_models import ReceiptFlowProfile, ReceiptFlowSnapshot
from app.v3.receipt_run_inputs import process_record
from app.v3.stock_receipts import ReceiptDelta, receipt_recipes, receipt_tokens


def catalog(profile: ReceiptFlowProfile, graph: Json) -> Json:
    flow = profile.flow
    value = light_catalog(flow, graph)
    value["initial_units"] = value.pop("units")
    value.pop("containers")
    value["initial_containers"] = [
        {
            "container_id": c.container_id,
            "recipe_id": c.recipe.recipe_id,
            "initial_owner_id": c.owner_id,
            "initial_sealed_for": c.sealed_for,
        }
        for c in sorted((*flow.stock.containers, *flow.materials), key=lambda c: c.container_id)
    ]
    tokens = {u.unit_id: u for u in flow.stock.units}
    wrappers = {c.container_id: c for c in flow.stock.containers}
    declared = []
    for offer in profile.receipts:
        unit, wrapper = receipt_recipes(offer.definition.sku_id, tokens, wrappers)
        declared.append(
            {
                **record(offer),
                "container_recipe_id": wrapper.recipe_id,
                "units": record(receipt_tokens(offer.definition, unit)),
                "existence": "declared_until_service_completion",
            }
        )
    value["declared_receipts"] = sorted(declared, key=lambda r: r["definition"]["receipt_id"])
    value["orders"] = record(flow.orders)
    value["receipt_process"] = process_record(profile)
    return value


def checkpoint(value: ReceiptFlowSnapshot) -> Json:
    inventory, stock = value.inventory, value.stock
    if any(
        canonical_bytes(record(getattr(stock, key)))
        != canonical_bytes(record(getattr(inventory, key)))
        for key in ("revision", "containers", "locations")
    ):
        raise ValueError("Native receipt stock and inventory views disagree")
    base = FlowSnapshot(**{f.name: getattr(value, f.name) for f in fields(FlowSnapshot)})
    result = light_checkpoint(base)
    state = result["state"]
    state["inventory"] = {
        "registered_receipt_ids": sorted(r.receipt_id for r in inventory.registered_receipts),
        "claims": record(inventory.claims),
        "claim_generation": inventory.claim_generation,
    }
    state["receipts"] = record(value.receipts)
    result["state_hash"] = sha256_hex(state)
    return result


def event(value: FlowEvent) -> Json:
    result = {f.name: record(getattr(value, f.name)) for f in fields(value) if f.name != "delta"}
    for key in ("receipt", "inventory_claim", "released_claim_id", "resource_id"):
        result.setdefault(key, None)
    result["delta"] = None
    if value.delta is not None:
        delta = stock_delta(value.delta)
        creation = value.delta if isinstance(value.delta, ReceiptDelta) else None
        delta.update(
            delta_type="receipt_creation" if creation else "stock",
            receipt=record(creation.receipt) if creation else None,
            created_tokens=record(creation.created_tokens) if creation else [],
        )
        result["delta"] = delta
    return result
