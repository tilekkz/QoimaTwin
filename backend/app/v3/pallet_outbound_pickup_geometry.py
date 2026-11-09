"""Actual pinned triangles, six continuous intervals and finite support patches."""

from dataclasses import replace
from hashlib import sha256

import numpy as np

from app.v3.mesh_proof_contact import contact_patch, support_margin
from app.v3.mesh_proof_covers import Cover, covers, merge_covers
from app.v3.mesh_proof_glb import load_glb
from app.v3.mesh_proof_motion import Pose, Segment, posed, select, validate_frames, validate_motion
from app.v3.mesh_proof_scene import RigidScene
from app.v3.mesh_proof_source import MESH_PATH
from app.v3.mesh_proof_sweeps import verify_segment
from app.v3.pallet_outbound_pickup_frames import cover_bounds, ry, world_box, world_point
from app.v3.pallet_outbound_pickup_identity import require
from app.v3.pallet_outbound_pickup_models import (
    PickupBounds,
    PickupContact,
    PickupPlan,
    PickupSource,
)
from app.v3.pallet_outbound_pickup_source import raw_document


def source_scene(source: PickupSource, plan: PickupPlan) -> RigidScene:
    raw = raw_document(source, "v3-mesh-proof-proposal", MESH_PATH)
    scene = load_glb(raw, sha256(raw).hexdigest(), allow_collinear=True)
    validate_frames(scene)
    nodes = []
    for node in scene.nodes:
        matrix = node.matrix.copy()
        if node.name == "pallet-load__HU":
            matrix[:3, :3] = np.diag([-1.0, 1.0, -1.0])
        nodes.append(replace(node, matrix=matrix))
    result = replace(scene, nodes=tuple(nodes))
    check_source_frame(result, plan)
    return result


def check_source_frame(scene: RigidScene, plan: PickupPlan) -> None:
    hu = next(n for n in scene.nodes if n.name == "pallet-load__HU")
    rotation = ry(plan.frame_yaw_rad)
    require(
        np.allclose(rotation @ hu.matrix[:3, :3], ry(plan.hu_yaw_rad), rtol=0, atol=2e-6),
        "Source HU signed axes changed",
    )
    require(
        np.allclose(world_point(plan, hu.matrix[:3, 3]), plan.hu_bottom_world, rtol=0, atol=2e-6),
        "Source HU bottom pose changed",
    )
    require(
        np.allclose(
            world_point(plan, np.array([0, 0, -1])), plan.source_root_world, rtol=0, atol=2e-6
        ),
        "Source prehandle transform changed",
    )


def mesh_segments(plan: PickupPlan) -> tuple[Segment, ...]:
    def pose(index: int, end: bool) -> Pose:
        value = plan.segments[index].end if end else plan.segments[index].start
        return Pose(float(value.root_z), float(value.fork_top), float(value.reach))

    result = tuple(
        Segment(s.ordinal, s.phase, pose(i, False), pose(i, True), s.attached)
        for i, s in enumerate(plan.segments)
    )
    validate_motion(result)
    return result


def check_sweeps(scene: RigidScene, segments: tuple[Segment, ...]) -> tuple[int, ...]:
    bounds = np.array([-0.8, 0, -2.5]), np.array([0.8, 2.1, 2.2])
    return tuple(verify_segment(scene, segment, bounds) for segment in segments)


def contacts_at(
    scene: RigidScene, pose: Pose, index: int, supports: tuple[str, ...]
) -> tuple[PickupContact, ...]:
    attached = index >= 3
    parts = posed(scene, pose, attached)
    cargo = tuple(p.triangles for p in select(scene, parts, "pallet-load__HU"))
    chosen = [select(scene, parts, name) for name in supports]
    require(all(chosen), "Required contact support absent")
    patches = tuple(
        contact_patch(tuple(p.triangles for p in group), cargo, pose.fork_top if attached else 0.18)
        for group in chosen
    )
    cog = (0.0, pose.root_z + 1 + pose.reach) if attached else (0.0, 1.4)
    margin = support_margin(patches, cog)
    return tuple(
        PickupContact(index, name, patch, margin)
        for name, patch in zip(supports, patches, strict=True)
    )


def check_contacts(scene: RigidScene, segments: tuple[Segment, ...]) -> tuple[PickupContact, ...]:
    poses = (segments[0].start, *(s.end for s in segments))
    result = contacts_at(scene, poses[0], 0, ("heavy-bay__MODULE",))
    for index in range(3, 7):
        result += contacts_at(scene, poses[index], index, ("joint__fork_L", "joint__fork_R"))
    return result


def action_bounds(
    scene: RigidScene, plan: PickupPlan, segments: tuple[Segment, ...]
) -> PickupBounds:
    hulls: list[Cover] = []
    for segment in segments:
        endpoints = [
            covers(scene, posed(scene, p, segment.attached), p)
            for p in (segment.start, segment.end)
        ]
        hulls.extend(merge_covers(*endpoints))
    return world_box(plan, *cover_bounds(hulls))
