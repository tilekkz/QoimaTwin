"""Shared decoded pinned documents; each corruption receives a fresh private tree."""

from pathlib import Path
from typing import Any

PACKAGE = Path(__file__).parents[2] / "data" / "v3-proposal"
PREFIX = "docs/v3/contract-proposals/"


def catalog_context(documents: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    cargo = {r["archetype_id"]: r for r in documents[PREFIX + "cargo-catalog-v3.json"]["records"]}
    skus = {s["sku_id"]: s for s in documents[PREFIX + "baseline-input-v3.json"]["skus"]}
    slots = {s["slot_id"]: s for s in documents[PREFIX + "storage-slots-v3.json"]["slots"]}
    ports = {
        p["port_id"]: p
        for d in ("inbound", "outbound")
        for p in documents[PREFIX + f"ports-v3.{d}.json"]["ports"]
    }
    return cargo, skus, slots, ports
