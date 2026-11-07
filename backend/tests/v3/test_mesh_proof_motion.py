"""Attachment continuity and source frames are checked independently of mesh color."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from app.v3.mesh_proof_motion import Pose, Segment, validate_frames, validate_motion
from app.v3.mesh_proof_source import load_fixture
from app.v3.mesh_proof_types import MeshProofError, readonly

SOURCE = Path(__file__).resolve().parents[2] / "data" / "v3-mesh-proof-proposal"


def test_attach_and_detach_preserve_cargo_world_pose() -> None:
    lower = Pose(0.0, 0.18, 0.4)
    lift = Pose(0.0, 0.7, 0.4)
    validate_motion(
        (Segment(0, "insert", lower, lower, False), Segment(1, "lift", lower, lift, True))
    )
    with pytest.raises(MeshProofError, match="attachment"):
        validate_motion(
            (Segment(0, "wrong", lift, lift, False), Segment(1, "lift", lift, lift, True))
        )


def test_motion_endpoint_discontinuity_fails() -> None:
    with pytest.raises(MeshProofError, match="continuous"):
        validate_motion(
            (
                Segment(0, "first", Pose(0.0, 0.7, 0.0), Pose(1.0, 0.7, 0.0), False),
                Segment(1, "second", Pose(2.0, 0.7, 0.0), Pose(3.0, 0.7, 0.0), False),
            )
        )


@pytest.mark.parametrize(
    "name", ["joint__reach", "heavy-bay__MODULE", "forklift-pallet-low-fixture"]
)
def test_changed_local_or_world_frame_cannot_reuse_proof(name: str) -> None:
    fixture = load_fixture(SOURCE)
    nodes = list(fixture.scene.nodes)
    index = next(i for i, node in enumerate(nodes) if node.name == name)
    moved = nodes[index].matrix.copy()
    moved[0, 3] += 0.01
    nodes[index] = replace(nodes[index], matrix=readonly(moved))
    with pytest.raises(MeshProofError, match=r"frame|transform"):
        validate_frames(replace(fixture.scene, nodes=tuple(nodes)))


def test_two_world_sweeps_overlap_but_common_translation_keeps_clearance() -> None:
    from app.v3.mesh_proof_geometry import empty_box
    from tests.v3.test_mesh_proof_geometry import box_triangles

    obstacle = box_triangles((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
    # Both move by ten metres. Relative positions remain separated by one metre.
    empty_box((obstacle,), np.array([2.0, 0.0, 0.0]), np.array([3.0, 1.0, 1.0]))
    with pytest.raises(MeshProofError):
        empty_box((obstacle,), np.array([0.5, 0.0, 0.0]), np.array([13.0, 1.0, 1.0]))
