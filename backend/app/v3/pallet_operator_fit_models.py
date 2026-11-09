"""Immutable conditional operator geometry, without runtime state or grants."""

from dataclasses import dataclass
from typing import Literal

from app.v3.mesh_proof_types import ContactPatch
from app.v3.pallet_outbound_pickup_models import PickupBounds, PickupSource, Vec3


@dataclass(frozen=True, slots=True)
class OperatorFitSource:
    pickup: PickupSource
    worker_raw: bytes
    provenance_raw: bytes
    source_hash: str


@dataclass(frozen=True, slots=True)
class OperatorAnchorFit:
    body_anchor: str
    vehicle_anchor: str
    body_to_vehicle_m: float
    vehicle_to_spec_m: float


@dataclass(frozen=True, slots=True)
class OperatorContact:
    support: str
    patch: ContactPatch


@dataclass(frozen=True, slots=True)
class OperatorFitChecks:
    body_solids: int
    vehicle_solids: int
    body_triangles: int
    anchors: tuple[OperatorAnchorFit, ...]
    contacts: tuple[OperatorContact, ...]
    helmet_roof_gap_m: float
    body_bounds_vehicle: PickupBounds
    interval_cover_checks: tuple[int, ...]
    wheel_cover_checks: int


@dataclass(frozen=True, slots=True)
class OperatorFitCertificate:
    method: str
    source_hash: str
    pickup_plan_hash: str
    actor_id: str
    vehicle_id: str
    pair_id: str
    worker_mesh_sha256: str
    vehicle_mesh_sha256: str
    checks: OperatorFitChecks
    conditional_body_root_world: Vec3
    limitations: tuple[str, ...]
    operational_admission: Literal[False]
    actual_initial_state_proved: Literal[False]
    boarding_path_proved: Literal[False]
    travel_admission: Literal[False]
    certificate_hash: str
