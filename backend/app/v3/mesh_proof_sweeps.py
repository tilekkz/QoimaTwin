"""Whole affine intervals tested in world and common-motion-relative frames."""

from dataclasses import replace

import numpy as np

from app.v3.mesh_proof_covers import Cover, covers, merge_covers
from app.v3.mesh_proof_geometry import empty_box
from app.v3.mesh_proof_motion import Pose, Segment, posed, select
from app.v3.mesh_proof_scene import RigidScene, Solid
from app.v3.mesh_proof_types import Array, MeshProofError


def _clear(hulls: tuple[Cover, ...], obstacles: tuple[Solid, ...], label: str) -> int:
    for hull in hulls:
        try:
            empty_box(tuple(part.triangles for part in obstacles), hull.low, hull.high)
        except MeshProofError as error:
            raise MeshProofError(f"{label}: {hull.name}: {error}") from error
    return len(hulls)


def _sweep(scene: RigidScene, segment: Segment, ancestor: str) -> tuple[Cover, ...]:
    states = tuple(
        select(scene, posed(scene, pose, segment.attached), ancestor)
        for pose in (segment.start, segment.end)
    )
    return merge_covers(
        covers(scene, states[0], segment.start), covers(scene, states[1], segment.end)
    )


def _attached(scene: RigidScene, segment: Segment) -> int:
    body = replace(
        segment, start=replace(segment.start, root_z=0), end=replace(segment.end, root_z=0)
    )
    vehicle = select(scene, posed(scene, body.end, True), "forklift_root")
    fixed = tuple(p for p in vehicle if "joint__carriage" not in scene.lineage(p.node))
    solids = tuple(
        p for p in fixed if not any(n.startswith("joint__wheel_") for n in scene.lineage(p.node))
    )
    wheels = tuple(p for p in fixed if p.name not in {s.name for s in solids})
    hulls = _sweep(scene, body, "pallet-load__HU")
    checked = _clear(hulls, solids, segment.phase + ":relative-body")
    for hull in hulls:
        for wheel in covers(scene, wheels, body.end):
            if not (np.any(hull.low >= wheel.high - 3e-7) or np.any(hull.high <= wheel.low + 3e-7)):
                raise MeshProofError("HU intersects full wheel envelope")
    carriage = replace(
        body, start=replace(body.start, fork_top=0), end=replace(body.end, fork_top=0)
    )
    vehicle = select(scene, posed(scene, carriage.end, True), "joint__carriage")
    fixed = tuple(p for p in vehicle if "joint__reach" not in scene.lineage(p.node))
    checked += _clear(_sweep(scene, carriage, "pallet-load__HU"), fixed, "relative-carriage")
    neutral = Pose(0, 0, 0)
    parts = posed(scene, neutral, True)
    checked += _clear(
        covers(scene, select(scene, parts, "joint__reach"), neutral),
        select(scene, parts, "pallet-load__HU"),
        "relative-reach",
    )
    return checked


def verify_segment(scene: RigidScene, segment: Segment, bounds: tuple[Array, Array]) -> int:
    platform = select(scene, posed(scene, segment.start, segment.attached), "heavy-bay__MODULE")
    vehicle = _sweep(scene, segment, "forklift_root")
    cargo = _sweep(scene, segment, "pallet-load__HU")
    for hull in vehicle + cargo:
        if np.any(hull.low < bounds[0] - 2e-6) or np.any(hull.high > bounds[1] + 2e-6):
            raise MeshProofError(f"outside isolated action space: {hull.name}")
        if hull.low[1] < -2e-6:
            raise MeshProofError("geometry below floor")
    checked = _clear(vehicle + cargo, platform, segment.phase + ":platform")
    if segment.attached:
        return checked + _attached(scene, segment)
    stock = select(scene, posed(scene, segment.start, False), "pallet-load__HU")
    return checked + _clear(vehicle, stock, segment.phase + ":stock")
