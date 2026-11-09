"""Immutable evidence for one conditional loaded reverse arc; no operational grant."""

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from app.v3.pallet_outbound_pickup_models import PickupBounds, PickupContact, PickupPose, Vec3

METHOD = "qoima-e011-first-loaded-arc-geometry-v1"
TravelStatus = Literal["NOT_ADMITTED_PENDING_EXPLICIT_PALLET_SIGNED_FRAME_BINDING"]
TRAVEL_STATUS: TravelStatus = "NOT_ADMITTED_PENDING_EXPLICIT_PALLET_SIGNED_FRAME_BINDING"


@dataclass(frozen=True, slots=True)
class ArcPlan:
    method: str
    source_hash: str
    pickup_plan_hash: str
    pickup_certificate_hash: str
    hu_id: str
    unit_ids: tuple[str, ...]
    actor_id: str
    vehicle_id: str
    arc_id: str
    from_node_id: str
    to_node_id: str
    start: PickupPose
    end: PickupPose
    root_start_world: Vec3
    root_end_world: Vec3
    axle_start_world: Vec3
    axle_end_world: Vec3
    source_yaw_rad: float
    motion_direction: Literal[-1]
    length_m: Fraction
    padding_m: Fraction
    top_padding_m: Fraction
    clear_height_m: Fraction
    destination_stop_allowed: None
    travel_orientation_status: TravelStatus
    operational_admission: Literal[False]
    plan_hash: str


@dataclass(frozen=True, slots=True)
class ArcGeometry:
    cover_checks: int
    moving_solids: int
    contacts: tuple[PickupContact, ...]
    bounds: PickupBounds
    endpoint_root_world: Vec3
    endpoint_axle_world: Vec3
    endpoint_hu_bottom_world: Vec3


@dataclass(frozen=True, slots=True)
class ArcObstacles:
    module_ids: tuple[str, ...]
    hu_ids: tuple[str, ...]
    minimum_module_gap_m: float
    minimum_hu_gap_m: float
    top_headroom_m: float
    within_envelope: Literal[True]


@dataclass(frozen=True, slots=True)
class ArcCertificate:
    method: str
    source_hash: str
    plan_hash: str
    mesh_sha256: str
    cover_checks: int
    moving_solids: int
    contacts: tuple[PickupContact, ...]
    bounds: PickupBounds
    obstacles: ArcObstacles
    endpoint_root_world: Vec3
    endpoint_axle_world: Vec3
    endpoint_hu_bottom_world: Vec3
    relative_hu_yaw_rad: float
    destination_stop_allowed: None
    travel_orientation_status: TravelStatus
    limitations: tuple[str, ...]
    operational_admission: Literal[False]
    certificate_hash: str
