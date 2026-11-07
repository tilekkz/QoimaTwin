"""Content identity, with quantities independent of placement (ADR 0008)."""

from typing import Any

from app.simulation.clock import TimeGrid
from app.simulation.context import RunInputs, SemanticJson
from app.storage.canonical_json import CANONICALIZATION_VERSION, sha256_hex
from app.version import ENGINE_VERSION

SET_KEYS = {
    "nodes": "node_id",
    "slots": "slot_id",
    "racks": "rack_id",
    "actors": "actor_id",
    "vehicles": "vehicle_id",
    "pack_stations": "pack_id",
    "inductions": "induction_id",
    "segments": "segment_id",
    "initial_lots": "lot_id",
    "lines": "sku_id",
}


def _normalize(value: Any, name: str = "") -> Any:
    if isinstance(value, dict):
        return {key: _normalize(item, key) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        if name in SET_KEYS:
            value = sorted(value, key=lambda item: item[SET_KEYS[name]])
        elif name in {"edges", "connections"}:
            value = sorted(value, key=sha256_hex)
        return [_normalize(item) for item in value]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _hash(value: Any) -> str:
    return sha256_hex(_normalize(value))


def _semantic_hash(value: SemanticJson | None) -> str:
    """Content hash of frozen semantic JSON (equals plan_id / forecast semantic_id); None if absent.

    Declared IDs are never trusted: SemanticJson recomputed the hash at construction.
    """
    return value.sha256 if value is not None else _hash(None)


def fingerprint(inputs: RunInputs, *, engine_version: str = ENGINE_VERSION) -> dict[str, Any]:
    lots = sorted(inputs.assignment.initial_lots, key=lambda lot: lot.lot_id)
    hashes = {
        "layout": _hash(inputs.layout.model_dump(mode="json", by_alias=True)),
        "config": _hash(inputs.config.model_dump(mode="json", by_alias=True)),
        "actors": _hash(inputs.actors.model_dump(mode="json")),
        "orders": _hash(
            [
                o.model_dump(mode="json")
                for o in sorted(inputs.scenario.orders, key=lambda o: (o.arrival_s, o.order_id))
            ]
        ),
        "receipts": _hash(
            [
                r.model_dump(mode="json")
                for r in sorted(inputs.scenario.receipts, key=lambda r: (r.arrival_s, r.receipt_id))
            ]
        ),
        "initial_inventory": _hash(
            [{"sku_id": lot.sku_id, "lot_id": lot.lot_id, "quantity": lot.quantity} for lot in lots]
        ),
        "assignment": _hash(
            {
                "active": inputs.assignment.active_assignment,
                "lots": [lot.model_dump(mode="json") for lot in lots],
            }
        ),
        "relocation_plan": _semantic_hash(inputs.relocation_json()),
        "forecast_snapshot": _semantic_hash(inputs.forecast_json()),
    }
    return {
        "canonicalization_version": CANONICALIZATION_VERSION,
        "identity_version": "qoima-run-v1",
        "engine_version": engine_version,
        "ticks_per_second": TimeGrid.for_inputs(inputs.layout, inputs.config).ticks_per_second,
        "horizon_s": _normalize(inputs.scenario.horizon_s),
        "scenario_id": inputs.scenario.scenario_id,
        "experiment_type": inputs.experiment_type,
        "hashes": hashes,
    }
