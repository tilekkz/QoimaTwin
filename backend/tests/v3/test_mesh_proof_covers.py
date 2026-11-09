"""A beveled L corner can leave the union even when every vertex lies in it."""

import numpy as np
import pytest

from app.v3.mesh_proof_covers import Cover, _fork_covers, covers, merge_covers
from app.v3.mesh_proof_motion import Pose
from app.v3.mesh_proof_scene import RigidNode, RigidScene, Solid
from app.v3.mesh_proof_types import MeshProofError, readonly


def test_fork_cover_contains_triangle_interior_at_concave_corner() -> None:
    triangles = np.array(
        [
            [[0.0, 0.0, 1.4], [0.0, 1.0, 0.4], [1.0, -1.0, -0.6]],
            [[0.0, -1.0, 0.4], [0.0, 0.0, 1.4], [1.0, 0.0, 0.4]],
            [[0.0, 0.0, -0.6], [0.0, 1.0, 0.4], [1.0, 0.0, 0.4]],
        ]
    )
    hulls = _fork_covers(Solid(0, "fork", triangles), Pose(0, 0, 0))
    midpoint = (triangles[0, 0] + triangles[0, 1]) / 2
    assert any(np.all(h.low <= midpoint) and np.all(midpoint <= h.high) for h in hulls)


def test_radial_wheel_cover_includes_mid_rotation_outside_endpoint_chord() -> None:
    triangles = np.array([[[-0.1, 0.0, 1.0], [0.1, 0.0, 1.0], [0.0, 0.0, 0.5]]])
    part = Solid(0, "wheel", readonly(triangles))
    scene = RigidScene(
        "hand", (RigidNode("joint__wheel_front_L", None, readonly(np.eye(4))),), (part,)
    )
    cover = covers(scene, (part,), Pose(0.0, 0.7, 0.0))[0]
    midpoint = np.array([0.0, 2**-0.5, 2**-0.5])
    assert midpoint[1] + midpoint[2] > 1  # Outside quarter-turn endpoint chord.
    assert np.all(cover.low <= midpoint) and np.all(midpoint <= cover.high)


def test_cover_cannot_change_which_triangles_it_encloses_during_segment() -> None:
    low, high = np.zeros(3), np.ones(3)
    with pytest.raises(MeshProofError, match="membership"):
        merge_covers(
            (Cover("fork:blade", low, high, (1,)),), (Cover("fork:blade", low, high, (2,)),)
        )
