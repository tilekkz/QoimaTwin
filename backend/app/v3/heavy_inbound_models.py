"""Immutable N2 offered additions; these records never credit inventory."""

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from app.v3.input_models import HandlingUnit
from app.v3.workload_models import TimedWorkload, WholeHUTemplate, WorkloadJob

VERSION = "qoima-n2-heavy-inbound-inputs-0.1.0"
SCOPE = "explicit_heavy_receipt_additions_to_unchanged_c10_offers"


@dataclass(frozen=True, slots=True)
class HeavyInboundReceipt:
    job_id: str
    hu_id: str
    lot_id: str
    sku_id: str
    port_id: str
    arrival_tick: int


@dataclass(frozen=True, slots=True)
class BoundHeavyReceipt:
    declaration: HeavyInboundReceipt
    offer: WorkloadJob
    template: WholeHUTemplate


@dataclass(frozen=True, slots=True)
class HeavyInboundDelta:
    archetype_id: str
    port_id: str
    before_count: int
    added_count: int
    after_count: int
    added_mass_kg: Fraction


@dataclass(frozen=True, slots=True)
class HeavyInboundAugmentation:
    receipts: tuple[BoundHeavyReceipt, ...]
    deltas: tuple[HeavyInboundDelta, ...]
    postshift_jobs: tuple[WorkloadJob, ...]


@dataclass(frozen=True, slots=True)
class HeavyInboundAuthority:
    source_revision: str
    layout_content_hash: str
    raw_fingerprints: tuple[tuple[str, str], ...]
    baseline_input_raw: bytes
    baseline_assignment_raw: bytes
    initial_hus: tuple[HandlingUnit, ...]
    baseline: TimedWorkload
    baseline_bytes: bytes


@dataclass(frozen=True, slots=True)
class HeavyInboundInputs:
    authority: HeavyInboundAuthority
    additions: tuple[HeavyInboundReceipt, ...]
    receipts: tuple[BoundHeavyReceipt, ...]
    deltas: tuple[HeavyInboundDelta, ...]
    postshift_jobs: tuple[WorkloadJob, ...]
    offered_bytes: bytes
    frozen_bytes: bytes
    input_hash: str
    accepted_receipt_count: Literal[0] = 0
    operational_admission: Literal[False] = False
    full_n2_acceptance: Literal[False] = False
