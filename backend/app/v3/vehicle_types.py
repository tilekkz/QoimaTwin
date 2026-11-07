"""Immutable vehicle geometry; no scheduler, mesh proof or operational grants."""

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

XZ = tuple[Fraction, Fraction]
XYZ = tuple[Fraction, Fraction, Fraction]


@dataclass(frozen=True, slots=True)
class ArcGeometry:
    kind: Literal["line", "rear_steer_arc"]
    start_yaw_rad: Fraction
    end_yaw_rad: Fraction
    start_xz: XZ | None = None
    end_xz: XZ | None = None
    icr_xz: XZ | None = None
    signed_radius_m: Fraction | None = None


@dataclass(frozen=True, slots=True)
class VehicleNode:
    node_id: str
    root_xyz: XYZ
    front_axle_xyz: XYZ
    yaw_rad: Fraction
    stop_allowed: bool | None


@dataclass(frozen=True, slots=True)
class VehicleArc:
    arc_id: str
    source: str
    target: str
    geometry: ArcGeometry
    motion_direction: int
    root_length_m: Fraction
    front_axle_length_m: Fraction
    equipment_pairs: frozenset[str]
    profiles: frozenset[str]
    cargo_classes: frozenset[str]
    source_groups: tuple[str, ...]
    traffic_groups: tuple[str, ...]
    clear_width_m: Fraction | None
    clear_height_m: Fraction
    clearance_ref: str | None
    rear_steer_deg: Fraction
    transition_rule: str
    source_ref: str


@dataclass(frozen=True, slots=True)
class VehicleResource:
    resource_id: str
    capacity: int
    vehicle_route_refs: tuple[str, ...] = ()
    human_route_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class VehicleGraph:
    layout_version: str
    axle_offset_m: Fraction
    nodes: Mapping[str, VehicleNode]
    arcs: Mapping[str, VehicleArc]
    resources: Mapping[str, VehicleResource]
    route_bindings: Mapping[str, tuple[str, ...]]

    @property
    def operational_admission(self) -> Literal[False]:
        return False
