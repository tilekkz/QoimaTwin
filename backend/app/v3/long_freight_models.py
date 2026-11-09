"""Immutable N3 prerequisite records; none authorizes a physical operation."""

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from app.v3.input_models import HandlingUnit
from app.v3.workload_models import XYZ, TimedWorkload

VERSION = "qoima-n3-long-freight-prerequisites-0.1.0"
SCOPE = "one_original_long_hu_static_requirements"
ORIGINAL_HU = "v3:HU:initial:DEMO_180:01"


@dataclass(frozen=True, slots=True)
class LongFreightRequest:
    hu_id: str
    source_slot_id: str
    target_slot_id: str
    orientation_id: str
    port_id: str
    pair_id: str
    actor_id: str
    vehicle_id: str


@dataclass(frozen=True, slots=True)
class LongFreightAuthority:
    source_revision: str
    layout_content_hash: str
    raw_fingerprints: tuple[tuple[str, str], ...]
    baseline_input_raw: bytes
    baseline_assignment_raw: bytes
    initial_hus: tuple[HandlingUnit, ...]
    workload: TimedWorkload
    workload_bytes: bytes


@dataclass(frozen=True, slots=True)
class LongFreightStatic:
    status: Literal["static_rejected", "prerequisites_only"]
    reasons: tuple[str, ...]
    required_dimensions_m: XYZ
    target_dimensions_m: XYZ
    hu_mass_kg: Fraction
    attachment_mass_kg: Fraction
    total_lifted_kg: Fraction
    port_clear_width_m: Fraction
    port_clear_height_m: Fraction
    port_service_seconds: Fraction | None
    pickup_design_passed: bool
    place_design_passed: bool


@dataclass(frozen=True, slots=True)
class LongFreightObligation:
    code: str
    required_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LongFreightRequirements:
    request: LongFreightRequest
    authority: LongFreightAuthority
    static: LongFreightStatic
    blockers: tuple[LongFreightObligation, ...]
    frozen_bytes: bytes
    input_hash: str
    operational_admission: Literal[False] = False
    full_n3_acceptance: Literal[False] = False
