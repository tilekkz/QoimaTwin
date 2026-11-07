"""L07 analytic interpolation and numeric consistency, not collision proof."""

import math
from dataclasses import dataclass
from fractions import Fraction

from .vehicle_types import ArcGeometry, VehicleArc, VehicleNode


@dataclass(frozen=True, slots=True)
class EvaluatedPose:
    root_xyz: tuple[float, float, float]
    front_axle_xyz: tuple[float, float, float]
    yaw_rad: float


def pose_at(geometry: ArcGeometry, progress: Fraction, axle_offset: Fraction) -> EvaluatedPose:
    if not isinstance(progress, Fraction) or not 0 <= progress <= 1:
        raise ValueError("vehicle progress must be an exact fraction in [0,1]")
    if not isinstance(axle_offset, Fraction) or axle_offset <= 0:
        raise ValueError("positive axle offset required")
    yaw = float(geometry.start_yaw_rad + progress * (geometry.end_yaw_rad - geometry.start_yaw_rad))
    if geometry.kind == "line":
        start, end = geometry.start_xz, geometry.end_xz
        if start is None or end is None or geometry.start_yaw_rad != geometry.end_yaw_rad:
            raise ValueError("line requires endpoints and constant physical yaw")
        x, z = (float(a + progress * (b - a)) for a, b in zip(start, end, strict=True))
    elif geometry.kind == "rear_steer_arc":
        if geometry.icr_xz is None or not geometry.signed_radius_m:
            raise ValueError("curve requires ICR and nonzero signed radius")
        q = float(geometry.signed_radius_m)
        x = float(geometry.icr_xz[0]) - q * math.cos(yaw)
        z = float(geometry.icr_xz[1]) + q * math.sin(yaw)
    else:
        raise ValueError("unknown vehicle analytic geometry")
    root = (x - float(axle_offset) * math.sin(yaw), 0.0, z - float(axle_offset) * math.cos(yaw))
    return EvaluatedPose(root, (x, 0.0, z), yaw)


def close(left: float, right: float) -> bool:
    """Floating source trig roundoff only; never a physical collision tolerance."""
    return math.isclose(left, right, rel_tol=1e-10, abs_tol=1e-9)


def _check_endpoint(pose: EvaluatedPose, node: VehicleNode) -> None:
    for actual, expected in zip(pose.root_xyz, node.root_xyz, strict=True):
        if not close(actual, float(expected)):
            raise ValueError("analytic root endpoint differs from source pose")
    for actual, expected in zip(pose.front_axle_xyz, node.front_axle_xyz, strict=True):
        if not close(actual, float(expected)):
            raise ValueError("analytic axle endpoint differs from source pose")
    difference = math.remainder(pose.yaw_rad - float(node.yaw_rad), 2 * math.pi)
    if not close(difference, 0):
        raise ValueError("analytic physical yaw differs from source pose")


def validate_arc_geometry(
    arc: VehicleArc, start: VehicleNode, end: VehicleNode, axle_offset: Fraction
) -> None:
    first = pose_at(arc.geometry, Fraction(0), axle_offset)
    last = pose_at(arc.geometry, Fraction(1), axle_offset)
    _check_endpoint(first, start)
    _check_endpoint(last, end)
    geometry = arc.geometry
    if geometry.kind == "line":
        dx = last.front_axle_xyz[0] - first.front_axle_xyz[0]
        dz = last.front_axle_xyz[2] - first.front_axle_xyz[2]
        axle_length = root_length = math.hypot(dx, dz)
        directed = dx * math.sin(first.yaw_rad) + dz * math.cos(first.yaw_rad)
        if not close(directed, arc.motion_direction * axle_length):
            raise ValueError("line motion direction conflicts with physical yaw")
    else:
        if geometry.signed_radius_m is None:
            raise ValueError("curve radius is absent")
        q, delta = float(geometry.signed_radius_m), last.yaw_rad - first.yaw_rad
        axle_length = abs(q * delta)
        root_length = abs(delta) * math.hypot(q, float(axle_offset))
        if q * delta * arc.motion_direction <= 0:
            raise ValueError("curve motion direction conflicts with yaw traversal")
    if not close(axle_length, float(arc.front_axle_length_m)):
        raise ValueError("analytic front axle length differs from declared length")
    if not close(root_length, float(arc.root_length_m)):
        raise ValueError("analytic root length differs from declared length")
