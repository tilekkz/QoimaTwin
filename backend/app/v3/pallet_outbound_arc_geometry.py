"""Reuse actual mesh continuous covers and pickup contact/frame helpers for one translation."""

import numpy as np

from app.v3.mesh_proof_covers import Cover, covers, merge_covers
from app.v3.mesh_proof_motion import Pose, Segment, posed, select
from app.v3.mesh_proof_scene import RigidScene
from app.v3.mesh_proof_sweeps import verify_segment
from app.v3.mesh_proof_types import Array
from app.v3.pallet_outbound_arc_models import ArcGeometry, ArcPlan
from app.v3.pallet_outbound_pickup_frames import cover_bounds, ry, vector, world_box, world_point
from app.v3.pallet_outbound_pickup_geometry import contacts_at
from app.v3.pallet_outbound_pickup_identity import require
from app.v3.pallet_outbound_pickup_models import PickupPlan, PickupSource
from app.v3.pallet_outbound_pickup_source import document


def mesh_segment(plan: ArcPlan) -> Segment:
    def pose(end: bool) -> Pose:
        value = plan.end if end else plan.start
        return Pose(float(value.root_z), float(value.fork_top), float(value.reach))

    return Segment(0, "first_source_loaded_reverse_arc", pose(False), pose(True), True)


def _bounds(source: PickupSource, pickup: PickupPlan) -> tuple[Array, Array]:
    envelope = document(source, "layout-v3.envelope.json")["bounds"]
    lo, hi = envelope["min"], envelope["max"]
    vertices = np.array(
        [[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    )
    local = (vertices - pickup.frame_origin_world) @ ry(pickup.frame_yaw_rad)
    return local.min(axis=0), local.max(axis=0)


def _moving(scene: RigidScene, segment: Segment) -> int:
    start, end = posed(scene, segment.start, True), posed(scene, segment.end, True)
    delta = np.array([0, 0, segment.end.root_z - segment.start.root_z])
    count = 0
    for a, b in zip(start, end, strict=True):
        lineage = scene.lineage(a.node)
        if "forklift_root" in lineage or "pallet-load__HU" in lineage:
            require(
                a.name == b.name
                and np.allclose(b.triangles - a.triangles, delta, rtol=0, atol=2e-12),
                "Actual carried geometry must share one rigid translation",
            )
            count += 1
    return count


def _hulls(scene: RigidScene, segment: Segment) -> tuple[Cover, ...]:
    endpoints = []
    for pose in (segment.start, segment.end):
        parts = posed(scene, pose, True)
        moving = select(scene, parts, "forklift_root") + select(scene, parts, "pallet-load__HU")
        endpoints.append(covers(scene, moving, pose))
    return merge_covers(*endpoints)


def check_geometry(
    scene: RigidScene,
    source: PickupSource,
    pickup: PickupPlan,
    plan: ArcPlan,
) -> ArcGeometry:
    segment = mesh_segment(plan)
    checks = verify_segment(scene, segment, _bounds(source, pickup))
    contacts = tuple(
        contact
        for index, pose in enumerate((segment.start, segment.end), 6)
        for contact in contacts_at(scene, pose, index, ("joint__fork_L", "joint__fork_R"))
    )
    bounds = world_box(pickup, *cover_bounds(_hulls(scene, segment)))
    root = world_point(pickup, np.array([0, 0, segment.end.root_z]))
    axle = vector(np.array(root) + ry(pickup.frame_yaw_rad) @ np.array([0, 0, 0.4]))
    require(
        np.allclose(root, plan.root_end_world, rtol=0, atol=2e-6)
        and np.allclose(axle, plan.axle_end_world, rtol=0, atol=2e-6),
        "Source root/axle endpoint mismatch",
    )
    hu = world_point(pickup, np.array([0, segment.end.fork_top, segment.end.root_z + 1]))
    return ArcGeometry(checks, _moving(scene, segment), contacts, bounds, root, axle, hu)
