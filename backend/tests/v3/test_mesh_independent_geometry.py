"""Independent hand geometry: exact convex volumes and whole-triangle covers."""

import numpy as np
import pytest

from app.v3.mesh_proof_covers import _fork_covers
from app.v3.mesh_proof_geometry import empty_box, triangle_box, validate_solid
from app.v3.mesh_proof_motion import Pose
from app.v3.mesh_proof_scene import Solid
from app.v3.mesh_proof_types import Array, MeshProofError


def cuboid(low: tuple[float, float, float], high: tuple[float, float, float]) -> Array:
    vertices = np.array(
        [
            [x, y, z]
            for x in (low[0], high[0])
            for y in (low[1], high[1])
            for z in (low[2], high[2])
        ],
        dtype=np.float64,
    )
    # Six outward oriented rectangles, independently triangulated on each diagonal.
    faces = np.array(
        [
            [0, 1, 2],
            [1, 3, 2],
            [4, 6, 5],
            [6, 7, 5],
            [0, 4, 1],
            [4, 5, 1],
            [2, 3, 6],
            [3, 7, 6],
            [0, 2, 4],
            [2, 6, 4],
            [1, 5, 3],
            [5, 7, 3],
        ]
    )
    return np.asarray(vertices[faces], dtype=np.float64)


def triangular_prism() -> Array:
    vertices = np.array(
        [[0, 0, 0], [2, 0, 0], [0, 0, 2], [0, 1, 0], [2, 1, 0], [0, 1, 2]], dtype=np.float64
    )
    # Material is 0<=y<=1, x>=0, z>=0, x+z<=2.
    faces = np.array(
        [[0, 1, 2], [3, 5, 4], [0, 3, 1], [3, 4, 1], [1, 4, 2], [4, 5, 2], [2, 5, 0], [5, 3, 0]]
    )
    return np.asarray(vertices[faces], dtype=np.float64)


def test_convex_prism_aabb_overlap_is_clear_but_contained_volume_is_not() -> None:
    prism = triangular_prism()
    validate_solid(prism)
    # Minimum x+z is 3>2: outside actual prism despite overlapping its AABB.
    empty_box((prism,), np.array([1.5, 0.2, 1.5]), np.array([1.8, 0.8, 1.8]))
    # All corners satisfy x+z<=.4<2 and lie strictly inside the material.
    with pytest.raises(MeshProofError, match="inside"):
        empty_box((prism,), np.array([0.1, 0.2, 0.1]), np.array([0.2, 0.8, 0.2]))


def test_triangle_intersection_uses_interior_not_only_its_vertices() -> None:
    triangle = np.array([[-1.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 2.0, 0.0]])
    low, high = np.array([-0.1, 0.9, -0.1]), np.array([0.1, 1.1, 0.1])
    assert not any(np.all(low <= vertex) and np.all(vertex <= high) for vertex in triangle)
    assert triangle_box(triangle, low, high)


def test_fork_triangle_vertices_in_l_union_do_not_hide_its_outside_interior() -> None:
    triangle = np.array([[[-0.1, 0.65, 1.8], [0.1, 1.65, 0.75], [0.05, 0.6, 0.7]]])
    hulls = _fork_covers(Solid(0, "hand-fork", triangle), Pose(0, 0.7, 0.4))
    midpoint = (triangle[0, 0] + triangle[0, 1]) / 2
    assert midpoint[1] > 0.7 and midpoint[2] > 0.8  # Outside both arms of the L.
    assert any(h.name.endswith(":corner") and h.triangle_indices == (0,) for h in hulls)
    # A convex cover containing every vertex contains every barycentric interior point.
    assert any(np.all(h.low <= triangle[0]) and np.all(triangle[0] <= h.high) for h in hulls)


def test_tiny_contact_inset_does_not_hide_a_resolved_penetration() -> None:
    block = cuboid((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
    validate_solid(block)
    empty_box((block,), np.array([1.0, 0.0, 0.0]), np.array([2.0, 1.0, 1.0]))
    with pytest.raises(MeshProofError, match="intrusion"):
        empty_box((block,), np.array([1.0 - 1e-5, 0.0, 0.0]), np.array([2.0, 1.0, 1.0]))
