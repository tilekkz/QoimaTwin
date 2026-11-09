"""Input-only fixture identity oracle, independent of app models and hashing helpers.

The rules are ADR 0008 plus the analytical adapter convention in ADR 0009 A27.
This deliberately reads source JSON and uses only the standard library. It does
not run the simulation or import app.exporter.identity / canonical_json.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

SOURCE_FILES = (
    "layout.example.json",
    "actors.example.json",
    "simulation_defaults.json",
    "analytical_fixture.json",
)
ID_FIELDS = {
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


def canonical_hash(value: Any) -> str:
    raw = json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _semantic(value: Any, field: str = "") -> Any:
    if isinstance(value, float):
        return int(value) if value.is_integer() else value
    if isinstance(value, dict):
        return {key: _semantic(child, key) for key, child in value.items()}
    if isinstance(value, list):
        items = value
        if field in ID_FIELDS:
            items = sorted(value, key=lambda row: row[ID_FIELDS[field]])
        elif field in {"edges", "connections"}:
            items = sorted(value, key=canonical_hash)
        return [_semantic(child) for child in items]
    return value


def _documents(contracts: Path) -> dict[str, Any]:
    docs = {
        name: json.loads((contracts / name).read_text(encoding="utf-8")) for name in SOURCE_FILES
    }
    layout = docs["layout.example.json"]
    graphs = [layout["picker_graph"], *layout["forklift_graphs"].values()]
    for graph in graphs:
        for edge in graph["edges"]:
            edge["length_m"] = float(edge["length_m"])
    for connection in layout["conveyor"]["connections"]:
        connection["at"] = [float(coordinate) for coordinate in connection["at"]]
    for actor in docs["actors.example.json"]["actors"]:
        for optional in ("home_node_id", "pack_id", "vehicle_id"):
            actor.setdefault(optional, None)
    return docs


def _preimages(docs: dict[str, Any]) -> dict[str, Any]:
    config = docs["simulation_defaults.json"]
    scenario = docs["analytical_fixture.json"]["scenario"]
    placement = scenario["assignment_override"]
    lots = sorted(
        [
            {
                "lot_id": "GROUND_" + sku,
                "sku_id": sku,
                "slot_id": slot,
                "quantity": config["ground_units_per_sku"],
            }
            for slot, sku in placement.items()
        ],
        key=lambda lot: lot["lot_id"],
    )
    return {
        "layout": docs["layout.example.json"],
        "config": config,
        "actors": docs["actors.example.json"],
        "orders": sorted(scenario["arrivals"], key=lambda row: (row["arrival_s"], row["order_id"])),
        "receipts": sorted(
            scenario["receipts"], key=lambda row: (row["arrival_s"], row["receipt_id"])
        ),
        "initial_inventory": [{k: v for k, v in lot.items() if k != "slot_id"} for lot in lots],
        "assignment": {"active": placement, "lots": lots},
        "relocation_plan": None,
        "forecast_snapshot": None,
    }


def build_fingerprint(contracts: Path) -> dict[str, Any]:
    docs = _documents(contracts)
    scenario = docs["analytical_fixture.json"]["scenario"]
    provenance = {
        "kind": "synthetic_fixture",
        "generator_version": "analytical-fixture-adapter-1",
        "seed": 0,
        "source_notes": "contracts/analytical_fixture.json",
        "orders_sha256": canonical_hash(scenario["arrivals"]),
        "receipts_sha256": canonical_hash(scenario["receipts"]),
    }
    return {
        "canonicalization_version": "qoima-json-v1",
        "identity_version": "qoima-run-v2",
        "engine_version": "qoima-engine-0.4.0",
        # 1,000,000 base resolution and thirds (e.g. 4m / 1.2mps) require lcm = 3,000,000.
        "ticks_per_second": 3_000_000,
        "horizon_s": 3600,
        "scenario_id": scenario["scenario_id"],
        "experiment_type": "fixture",
        "provenance_sha256": canonical_hash(provenance),
        "hashes": {
            key: canonical_hash(_semantic(value)) for key, value in _preimages(docs).items()
        },
    }


def source_hashes(contracts: Path) -> dict[str, str]:
    """Text digests normalize CRLF to LF so Git checkout EOLs do not affect the golden."""
    return {
        name: hashlib.sha256((contracts / name).read_text(encoding="utf-8").encode()).hexdigest()
        for name in SOURCE_FILES
    }
