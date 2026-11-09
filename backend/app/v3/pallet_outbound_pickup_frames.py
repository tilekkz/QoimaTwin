"""Pure fixed-yaw coordinate conversions; source rotation is never silently inherited."""

import math
from collections.abc import Sequence

import numpy as np

from app.v3.mesh_proof_covers import Cover
from app.v3.mesh_proof_types import Array
from app.v3.pallet_outbound_pickup_models import PickupBounds, PickupPlan, Vec3


def ry(yaw: float) -> Array:
    return np.array(
        [[math.cos(yaw), 0.0, math.sin(yaw)], [0.0, 1.0, 0.0], [-math.sin(yaw), 0.0, math.cos(yaw)]]
    )


def vector(value: Array) -> Vec3:
    return float(value[0]), float(value[1]), float(value[2])


def world_point(plan: PickupPlan, value: Array) -> Vec3:
    return vector(np.array(plan.frame_origin_world) + ry(plan.frame_yaw_rad) @ value)


def cover_bounds(hulls: Sequence[Cover]) -> tuple[Array, Array]:
    low = np.array([h.low for h in hulls], dtype=np.float64).min(axis=0)
    high = np.array([h.high for h in hulls], dtype=np.float64).max(axis=0)
    return low, high


def world_box(plan: PickupPlan, low: Array, high: Array) -> PickupBounds:
    vertices = np.array(
        [[x, y, z] for x in (low[0], high[0]) for y in (low[1], high[1]) for z in (low[2], high[2])]
    )
    vertices = vertices @ ry(plan.frame_yaw_rad).T + plan.frame_origin_world
    return PickupBounds(vector(vertices.min(axis=0)), vector(vertices.max(axis=0)))
