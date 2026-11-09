"""Immutable whole-HU offers and demand; these values never allocate warehouse stock."""

from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Literal

Direction = Literal["inbound", "outbound"]
Hashes = tuple[tuple[str, str], ...]
XYZ = tuple[Fraction, Fraction, Fraction]


@dataclass(frozen=True, slots=True)
class DemandWeight:
    sku_id: str
    port_id: str
    weight: Fraction


@dataclass(frozen=True, slots=True)
class Quota:
    sku_id: str
    port_id: str
    expected: Fraction
    count: int
    delta: Fraction


@dataclass(frozen=True, slots=True)
class BurstWindow:
    start_tick: int
    end_tick: int
    weight: Fraction


@dataclass(frozen=True, slots=True)
class WorkloadPolicy:
    horizon_tick: int
    inbound_hus: int
    outbound_hus: int
    calendar: Literal["normal", "burst"]
    windows: tuple[BurstWindow, ...] = ()


@dataclass(frozen=True, slots=True)
class WholeHUTemplate:
    sku_id: str
    archetype_id: str
    quantity_units: int
    dimensions_xyz_m: XYZ
    gross_mass_kg: Fraction
    orientation_id: str
    source_lot_id: str
    initial_hu_ids: tuple[str, ...]
    cargo_record_sha256: str
    packing_recipe_sha256: str


@dataclass(frozen=True, slots=True)
class WorkloadSource:
    source_revision: str
    layout_content_hash: str
    raw_fingerprints: Hashes
    document_fingerprints: Hashes
    templates: tuple[WholeHUTemplate, ...]
    inbound_weights: tuple[DemandWeight, ...]
    outbound_weights: tuple[DemandWeight, ...]


@dataclass(frozen=True, slots=True)
class WorkloadJob:
    job_id: str
    direction: Direction
    sku_id: str
    archetype_id: str
    template_id: str
    port_id: str
    quantity_units: int
    arrival_tick: int
    hu_id: str | None
    lot_id: str | None


@dataclass(frozen=True, slots=True)
class TimedWorkload:
    source: WorkloadSource
    policy: WorkloadPolicy
    inbound_quotas: tuple[Quota, ...]
    outbound_quotas: tuple[Quota, ...]
    jobs: tuple[WorkloadJob, ...]
    population_id: str
    workload_id: str

    def to_dict(self) -> dict[str, Any]:
        from app.v3.workload_wire import workload_dict

        return workload_dict(self)

    @property
    def operational_admission(self) -> Literal[False]:
        return False
