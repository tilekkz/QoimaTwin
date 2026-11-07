"""Exercise the public segment checker in real relative frames, not just endpoint boxes."""

import numpy as np
import pytest

from app.v3.mesh_proof_motion import Pose, Segment, validate_motion
from app.v3.mesh_proof_scene import RigidNode, RigidScene, Solid
from app.v3.mesh_proof_sweeps import verify_segment
from app.v3.mesh_proof_types import Array, MeshProofError, readonly
from tests.v3.test_mesh_independent_geometry import cuboid

BOUNDS = np.array([-3.0, 0.0, -3.0]), np.array([3.0, 3.0, 16.0])


def hand_scene(part: Array, *, parent: int = 1) -> RigidScene:
    nodes = tuple(
        RigidNode(name, owner, readonly(np.eye(4)))
        for name, owner in (
            ("fixture", None),
            ("forklift_root", 0),
            ("joint__carriage", 1),
            ("joint__reach", 2),
            ("pallet-load__HU", 0),
        )
    )
    parts = (
        Solid(parent, "hand-vehicle-solid", readonly(part)),
        Solid(4, "hand-cargo", readonly(cuboid((-0.1, 0.0, 0.0), (0.1, 0.2, 0.2)))),
    )
    return RigidScene("hand-geometry", nodes, parts)


def endpoint_check(scene: RigidScene, segment: Segment) -> None:
    for pose in (segment.start, segment.end):
        assert (
            verify_segment(scene, Segment(0, "endpoint", pose, pose, segment.attached), BOUNDS) > 0
        )


def test_detached_hu_interference_is_rejected_between_clear_endpoints() -> None:
    scene = hand_scene(cuboid((-0.1, 0.2, -0.1), (0.1, 0.4, 0.1)))
    segment = Segment(0, "hand-insertion", Pose(0.0, 0.7, 0.0), Pose(2.0, 0.7, 0.0), False)
    endpoint_check(scene, segment)
    with pytest.raises(MeshProofError, match="stock"):
        verify_segment(scene, segment, BOUNDS)


def test_attached_common_root_motion_keeps_gap_despite_overlapping_world_sweeps() -> None:
    scene = hand_scene(cuboid((-0.1, 0.0, 0.0), (0.1, 1.0, 0.5)))
    segment = Segment(0, "hand-travel", Pose(0.0, 0.5, 0.0), Pose(10.0, 0.5, 0.0), True)
    # Body z[0,.5] and HU z[1,1.2] remain separated by.5 while translating together.
    assert verify_segment(scene, segment, BOUNDS) > 0


def test_reach_change_cannot_tunnel_through_body_after_common_root_is_removed() -> None:
    scene = hand_scene(cuboid((-0.1, 0.0, 2.0), (0.1, 1.0, 2.2)))
    segment = Segment(0, "hand-relative-reach", Pose(0.0, 0.5, 0.0), Pose(10.0, 0.5, 2.0), True)
    endpoint_check(scene, segment)
    with pytest.raises(MeshProofError, match="relative-body"):
        verify_segment(scene, segment, BOUNDS)


def test_common_carriage_lift_keeps_relative_gap() -> None:
    scene = hand_scene(cuboid((-0.1, 0.5, 0.96), (0.1, 0.7, 1.16)), parent=2)
    segment = Segment(0, "hand-lift", Pose(0.0, 0.5, 0.0), Pose(10.0, 1.5, 0.0), True)
    # Carriage solid and HU share root and lift; their vertical gap stays.3.
    assert verify_segment(scene, segment, BOUNDS) > 0


def test_relative_reach_cannot_tunnel_through_carriage_mid_interval() -> None:
    scene = hand_scene(cuboid((-0.1, 0.0, 1.96), (0.1, 1.0, 2.16)), parent=2)
    segment = Segment(0, "hand-carriage", Pose(0.0, 0.5, 0.0), Pose(10.0, 1.5, 2.0), True)
    endpoint_check(scene, segment)
    with pytest.raises(MeshProofError, match="relative-carriage"):
        verify_segment(scene, segment, BOUNDS)


def test_attachment_rejects_five_centimetre_world_pose_jump() -> None:
    pose = Pose(0.05, 0.18, 0.4)
    with pytest.raises(MeshProofError, match="attachment"):
        validate_motion(
            (Segment(0, "unattached", pose, pose, False), Segment(1, "attached", pose, pose, True))
        )
