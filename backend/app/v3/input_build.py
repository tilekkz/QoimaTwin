"""Build public frozen models only after all static validation succeeds."""

import json
from types import MappingProxyType
from typing import Any

from .input_checks import get_document
from .input_models import (
    SKU,
    BaselineStats,
    CargoArchetype,
    HandlingUnit,
    ImmutableDocument,
    Port,
    SourceInventoryEntry,
    StorageSlot,
    V3Bundle,
)
from .input_pin import LAYOUT_CONTENT_HASH, SOURCE_REVISION


def xyz(value: Any) -> tuple[float, float, float]:
    return float(value[0]), float(value[1]), float(value[2])


def build_bundle(
    documents: dict[str, Any], inventory: tuple[SourceInventoryEntry, ...], stats: BaselineStats
) -> V3Bundle:
    cargo = tuple(
        build_cargo(row) for row in get_document(documents, "cargo-catalog-v3.json")["records"]
    )
    masses = {c.archetype_id: c.gross_mass_kg for c in cargo}
    skus = tuple(build_sku(s) for s in get_document(documents, "baseline-input-v3.json")["skus"])
    units = tuple(
        build_unit(a, masses)
        for a in get_document(documents, "baseline-assignment-v3.json")["assignments"]
    )
    slots = tuple(build_slot(s) for s in get_document(documents, "storage-slots-v3.json")["slots"])
    ports = tuple(
        build_port(p)
        for direction in ("inbound", "outbound")
        for p in get_document(documents, f"ports-v3.{direction}.json")["ports"]
    )
    frozen = MappingProxyType(
        {
            name: ImmutableDocument(
                json.dumps(
                    data,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")
            )
            for name, data in documents.items()
        }
    )
    return V3Bundle(
        SOURCE_REVISION,
        LAYOUT_CONTENT_HASH,
        inventory,
        frozen,
        skus,
        cargo,
        units,
        slots,
        ports,
        stats,
    )


def build_cargo(row: dict[str, Any]) -> CargoArchetype:
    hu = row["handling_unit"]
    return CargoArchetype(
        row["archetype_id"],
        xyz(row["unit"]["dimensions_xyz_m"]),
        row["unit"]["gross_mass_kg"],
        xyz(hu["dimensions_xyz_m"]),
        hu["gross_mass_kg"],
        hu["units_per_handling_unit"],
        tuple(row["compatibility"]["storage_type_tags"]),
    )


def build_port(row: dict[str, Any]) -> Port:
    return Port(
        row["port_id"],
        row["direction"],
        xyz(row["world_pos"]),
        row["service_node_id"],
        row["finite_buffer_capacity"]["total"],
        row["service_capacity"]["max_concurrent_jobs"],
        tuple(row["allowed_cargo_archetype_ids"]),
        tuple(sorted(row["service_time_rule"]["seconds_by_archetype"].items())),
        tuple((float(w[0]), float(w[1])) for w in row["open_windows"]),
    )


def build_sku(s: dict[str, Any]) -> SKU:
    return SKU(
        s["sku_id"],
        s["archetype_id"],
        s["lot_id"],
        s["quantity_units"],
        tuple(s["handling_unit_ids"]),
    )


def build_unit(a: dict[str, Any], masses: dict[str, float]) -> HandlingUnit:
    return HandlingUnit(
        a["handling_unit_id"],
        a["sku_id"],
        a["archetype_id"],
        a["lot_id"],
        a["slot_id"],
        a["module_id"],
        a["quantity_units"],
        masses[a["archetype_id"]],
        a["orientation_id"],
    )


def build_slot(s: dict[str, Any]) -> StorageSlot:
    return StorageSlot(
        s["slot_id"],
        s["module_id"],
        s["storage_type"],
        s["active_pick_candidate"],
        s["reserve_only"],
        s["retrieval_blocked"],
        s["max_payload_kg"],
        xyz(s["usable_dimensions_xyz_m"]),
        tuple(s["allowed_cargo_archetype_ids"]),
    )
