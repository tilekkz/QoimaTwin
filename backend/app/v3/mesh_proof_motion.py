"""Dimensionless local action states; published visual seconds are not engine time."""

from dataclasses import dataclass
from itertools import pairwise

import numpy as np

from app.v3.mesh_proof_scene import RigidScene, Solid
from app.v3.mesh_proof_types import Array, MeshProofError


@dataclass(frozen=True, slots=True)
class Pose:
    root_z: float
    fork_top: float
    reach: float


@dataclass(frozen=True, slots=True)
class Segment:
    ordinal: int
    phase: str
    start: Pose
    end: Pose
    attached: bool


def translations(pose: Pose, attached: bool) -> dict[str, Array]:
    values = [pose.root_z, pose.fork_top, pose.reach]
    if any(type(v) not in (int, float) for v in values) or not np.isfinite(values).all():
        raise MeshProofError("nonfinite action pose")
    return {
        "forklift_root": np.array([0.0, 0.0, pose.root_z]),
        "joint__carriage": np.array([0.0, pose.fork_top, 0.04]),
        "joint__reach": np.array([0.0, 0.0, 0.36 + pose.reach]),
        "joint__fork_L": np.array([-0.4, 0.0, 0.0]),
        "joint__fork_R": np.array([0.4, 0.0, 0.0]),
        "pallet-load__HU": np.array(
            [0.0, pose.fork_top, pose.root_z + 1 + pose.reach] if attached else [0.0, 0.18, 1.4]
        ),
    }


def posed(scene: RigidScene, pose: Pose, attached: bool) -> tuple[Solid, ...]:
    return scene.world_parts(translations(pose, attached))


def select(scene: RigidScene, parts: tuple[Solid, ...], ancestor: str) -> tuple[Solid, ...]:
    return tuple(part for part in parts if ancestor in scene.lineage(part.node))


def validate_frames(scene: RigidScene) -> None:
    expected = {
        "forklift_root": ("forklift-pallet-low-fixture", [0.0, 0.0, 0.0]),
        "joint__carriage": ("forklift_root", [0.0, 0.18, 0.04]),
        "joint__reach": ("joint__carriage", [0.0, 0.0, 0.76]),
        "joint__fork_L": ("joint__reach", [-0.4, 0.0, 0.0]),
        "joint__fork_R": ("joint__reach", [0.4, 0.0, 0.0]),
        "pallet-load__HU": ("forklift-pallet-low-fixture", [0.0, 0.18, 1.4]),
        "anchor_cog_declared": ("pallet-load__HU", [0.0, 0.675, 0.0]),
    }
    nodes = {node.name: node for node in scene.nodes}
    root = nodes.get("forklift-pallet-low-fixture")
    if root is None or root.parent is not None or not np.array_equal(root.matrix, np.eye(4)):
        raise MeshProofError("wrong fixture root frame")
    for name, (parent, xyz) in expected.items():
        node = nodes.get(name)
        if node is None or node.parent is None or scene.nodes[node.parent].name != parent:
            raise MeshProofError(f"wrong semantic frame: {name}")
        matrix = np.eye(4)
        matrix[:3, 3] = xyz
        if not np.allclose(node.matrix, matrix, rtol=0, atol=2e-6):
            raise MeshProofError(f"wrong node transform: {name}")
    platform = nodes.get("heavy-bay__MODULE")
    if (
        platform is None
        or not np.allclose(platform.matrix[:3, 3], [0, 0, 1.5], atol=2e-6, rtol=0)
        or not np.allclose(platform.matrix[:3, :3], np.diag([-1, 1, -1]), atol=2e-6, rtol=0)
    ):
        raise MeshProofError("wrong platform frame")


def validate_motion(segments: tuple[Segment, ...]) -> None:
    if not segments:
        raise MeshProofError("empty motion")
    for segment in segments:
        for pose in (segment.start, segment.end):
            translations(pose, segment.attached)
    for first, second in pairwise(segments):
        if first.end != second.start:
            raise MeshProofError("motion must be continuous")
        before = translations(first.end, first.attached)["pallet-load__HU"]
        after = translations(second.start, second.attached)["pallet-load__HU"]
        if not np.allclose(before, after, rtol=0, atol=2e-6):
            raise MeshProofError("attachment changes HU world pose")
