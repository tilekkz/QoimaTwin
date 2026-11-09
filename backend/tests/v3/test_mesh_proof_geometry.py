"""Independent metric boxes and contact patches, unrelated to engine output."""

import numpy as np
import pytest
from numpy.typing import NDArray

from app.v3.mesh_proof_geometry import empty_box, triangle_box, validate_solid
from app.v3.mesh_proof_types import MeshProofError


def box_triangles(low: tuple[float, ...], high: tuple[float, ...]) -> NDArray[np.float64]:
    points = np.array(
        [
            [x, y, z]
            for x in (low[0], high[0])
            for y in (low[1], high[1])
            for z in (low[2], high[2])
        ],
        dtype=np.float64,
    )
    faces = ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3))
    return np.asarray(
        points[np.array([(a, b, c) for a, b, c, _ in faces] + [(a, c, d) for a, _, c, d in faces])],
        dtype=np.float64,
    )


def test_closed_box_and_touch_are_allowed_but_penetration_is_not() -> None:
    solid = box_triangles((0, 0, 0), (1, 1, 1))
    validate_solid(solid)
    empty_box((solid,), np.array([1.0, 0.0, 0.0]), np.array([2.0, 1.0, 1.0]))
    with pytest.raises(MeshProofError, match="intrusion"):
        empty_box((solid,), np.array([0.9, 0.0, 0.0]), np.array([2.0, 1.0, 1.0]))


def test_contained_hull_is_rejected_without_surface_crossing() -> None:
    solid = box_triangles((0, 0, 0), (2, 2, 2))
    with pytest.raises(MeshProofError, match="inside"):
        empty_box((solid,), np.array([0.5, 0.5, 0.5]), np.array([1.5, 1.5, 1.5]))


@pytest.mark.parametrize("mutation", ["open", "reversed", "degenerate", "nonfinite"])
def test_invalid_solid_is_rejected(mutation: str) -> None:
    solid = box_triangles((0, 0, 0), (1, 1, 1))
    if mutation == "open":
        solid = solid[:-1]
    elif mutation == "reversed":
        solid = solid[:, ::-1]
    elif mutation == "degenerate":
        solid[0, 1] = solid[0, 0]
    else:
        solid[0, 0, 0] = np.nan
    with pytest.raises(MeshProofError):
        validate_solid(solid)


def test_triangle_sat_rejects_aabb_false_positive() -> None:
    triangle = np.array([[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [0.0, 2.0, 0.0]])
    assert not triangle_box(triangle, np.array([1.5, 1.5, -0.1]), np.array([2.0, 2.0, 0.1]))


def test_swept_hull_catches_tunneling_missed_by_endpoints() -> None:
    obstacle = box_triangles((1, 0, 0), (2, 1, 1))
    empty_box((obstacle,), np.array([-1.0, 0.0, 0.0]), np.array([0.0, 1.0, 1.0]))
    empty_box((obstacle,), np.array([3.0, 0.0, 0.0]), np.array([4.0, 1.0, 1.0]))
    with pytest.raises(MeshProofError):
        empty_box((obstacle,), np.array([-1.0, 0.0, 0.0]), np.array([4.0, 1.0, 1.0]))


def test_explicit_collinear_policy_retains_closed_topology_and_solid_detection() -> None:
    solid = box_triangles((0, 0, 0), (2, 2, 2))
    a, b, c = solid[0]
    middle = (a + b) / 2
    triangulated = np.concatenate(
        (np.array([[a, middle, c], [middle, b, c], [a, b, middle]]), solid[1:])
    )
    with pytest.raises(MeshProofError, match="degenerate"):
        validate_solid(triangulated)
    validate_solid(triangulated, allow_collinear=True)
    with pytest.raises(MeshProofError, match="inside"):
        empty_box((triangulated,), np.array([0.5, 0.5, 0.5]), np.array([1.5, 1.5, 1.5]))
