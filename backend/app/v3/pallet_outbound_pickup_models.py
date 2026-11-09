"""Immutable, geometry-only E011 pickup evidence; no operational state or clock."""

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from app.v3.mesh_proof_types import ContactPatch

Vec3 = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class PickupDocument:
    package: str
    path: str
    raw: bytes


@dataclass(frozen=True, slots=True)
class PickupSource:
    documents: tuple[PickupDocument, ...]
    source_hash: str


@dataclass(frozen=True, slots=True)
class PickupPose:
    root_z: Fraction
    fork_top: Fraction
    reach: Fraction


@dataclass(frozen=True, slots=True)
class PickupSegment:
    ordinal: int
    phase: str
    start: PickupPose
    end: PickupPose
    attached: bool


@dataclass(frozen=True, slots=True)
class PickupPlan:
    method: str
    source_hash: str
    hu_id: str
    slot_id: str
    module_id: str
    sku_id: str
    lot_id: str
    unit_ids: tuple[str, ...]
    actor_id: str
    vehicle_id: str
    source_root_world: Vec3
    source_yaw_rad: float
    frame_origin_world: Vec3
    frame_yaw_rad: float
    hu_bottom_world: Vec3
    hu_yaw_rad: float
    segments: tuple[PickupSegment, ...]
    pose_policy: str
    operational_admission: Literal[False]
    positive_fore_aft_clearance: Literal[False]
    plan_hash: str


@dataclass(frozen=True, slots=True)
class PickupBounds:
    low: Vec3
    high: Vec3


@dataclass(frozen=True, slots=True)
class PickupContact:
    pose_index: int
    support: str
    patch: ContactPatch
    support_margin_m: float


@dataclass(frozen=True, slots=True)
class PickupObstacles:
    module_ids: tuple[str, ...]
    hu_ids: tuple[str, ...]
    minimum_axis_gap_m: float
    within_envelope: bool


@dataclass(frozen=True, slots=True)
class PickupCertificate:
    method: str
    source_hash: str
    plan_hash: str
    mesh_sha256: str
    action_sha256: str
    segment_cover_checks: tuple[int, ...]
    contacts: tuple[PickupContact, ...]
    action_bounds: PickupBounds
    endpoint_bounds: PickupBounds
    hu_endpoint_bounds: PickupBounds
    obstacles: PickupObstacles
    endpoint_root_world: Vec3
    endpoint_axle_world: Vec3
    first_arc_id: str
    relative_hu_yaw_rad: float
    travel_orientation_status: Literal["not_admitted_pending_C08_relative_yaw_frame_binding"]
    limitations: tuple[str, ...]
    operational_admission: Literal[False]
    positive_fore_aft_clearance: Literal[False]
    certificate_hash: str
