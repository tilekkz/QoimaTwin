"""Immutable public value objects for the pinned static proposal."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal


class V3InputError(ValueError):
    """A source path and precise validation failure, safe to display to callers."""


@dataclass(frozen=True, slots=True)
class ImmutableDocument:
    canonical_bytes: bytes

    def decode(self) -> Any:
        """Return a fresh JSON tree; edits never change the frozen document."""
        return json.loads(self.canonical_bytes)


@dataclass(frozen=True, slots=True)
class SourceInventoryEntry:
    path: str
    raw_sha256: str
    bytes: int


@dataclass(frozen=True, slots=True)
class SKU:
    sku_id: str
    archetype_id: str
    lot_id: str
    quantity_units: int
    handling_unit_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CargoArchetype:
    archetype_id: str
    unit_dimensions_xyz_m: tuple[float, float, float]
    unit_gross_mass_kg: float
    dimensions_xyz_m: tuple[float, float, float]
    gross_mass_kg: float
    units_per_handling_unit: int
    allowed_storage_types: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HandlingUnit:
    handling_unit_id: str
    sku_id: str
    archetype_id: str
    lot_id: str
    slot_id: str
    module_id: str
    quantity_units: int
    gross_mass_kg: float
    orientation_id: str


@dataclass(frozen=True, slots=True)
class StorageSlot:
    slot_id: str
    module_id: str
    storage_type: str
    active_pick_candidate: bool
    reserve_only: bool
    retrieval_blocked: bool
    max_payload_kg: float
    usable_dimensions_xyz_m: tuple[float, float, float]
    allowed_cargo_archetype_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Port:
    port_id: str
    direction: Literal["inbound", "outbound"]
    world_pos: tuple[float, float, float]
    service_node_id: str
    buffer_capacity: int
    max_concurrent_jobs: int
    allowed_cargo_archetype_ids: tuple[str, ...]
    seconds_by_archetype: tuple[tuple[str, float], ...]
    open_windows: tuple[tuple[float, float], ...]


@dataclass(frozen=True, slots=True)
class BaselineStats:
    sku_count: int
    handling_units: int
    occupied_slots: int
    physical_slots: int
    active_slots: int
    blocked_reserve_slots: int
    free_active_slots: int
    free_initial_flex_slots: int
    quantity_units: int
    gross_mass_kg: float


@dataclass(frozen=True, slots=True)
class V3Bundle:
    source_revision: str
    layout_content_hash: str
    source_inventory: tuple[SourceInventoryEntry, ...]
    documents: Mapping[str, ImmutableDocument]
    skus: tuple[SKU, ...]
    cargo_archetypes: tuple[CargoArchetype, ...]
    handling_units: tuple[HandlingUnit, ...]
    slots: tuple[StorageSlot, ...]
    ports: tuple[Port, ...]
    baseline: BaselineStats
    data_kind: Literal["static_geometry_proposal"] = "static_geometry_proposal"
    operational_admission: Literal[False] = False
