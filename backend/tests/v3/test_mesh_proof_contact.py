"""Finite-area support must not be inferred from two ray hits."""

import numpy as np
import pytest

from app.v3.mesh_proof_contact import contact_patch, support_margin
from app.v3.mesh_proof_types import MeshProofError
from tests.v3.test_mesh_proof_geometry import box_triangles


def test_exact_rectangular_contact_area_and_centroid() -> None:
    support = box_triangles((-0.04, -0.07, -0.5), (0.04, 0, 0.5))
    cargo = box_triangles((-0.5, 0, -0.1), (0.5, 0.2, 0.1))
    patch = contact_patch((support,), (cargo,), 0.0)
    assert patch.area_m2 == pytest.approx(0.08 * 0.2, abs=1e-14)
    np.testing.assert_allclose(patch.centroid_xz, (0.0, 0.0), atol=1e-14)


def test_touching_edge_has_no_support_area() -> None:
    support = box_triangles((0, -1, 0), (1, 0, 1))
    cargo = box_triangles((1, 0, 0), (2, 1, 1))
    with pytest.raises(MeshProofError, match="contact area"):
        contact_patch((support,), (cargo,), 0.0)


@pytest.mark.parametrize("height", [0.001, -0.001])
def test_contact_requires_matching_plane_with_bounded_residual(height: float) -> None:
    support = box_triangles((0, -1, 0), (1, 0, 1))
    cargo = box_triangles((0, height, 0), (1, height + 1, 1))
    with pytest.raises(MeshProofError):
        contact_patch((support,), (cargo,), 0.0)


def test_overlapping_surfaces_cannot_double_count_support_area() -> None:
    support = box_triangles((0, -1, 0), (1, 0, 1))
    cargo = box_triangles((0, 0, 0), (1, 1, 1))
    with pytest.raises(MeshProofError, match="overlapping"):
        contact_patch((support, support), (cargo,), 0.0)


def test_combined_support_contains_cog_with_measured_margin() -> None:
    cargo = box_triangles((-1, 0, -1), (1, 1, 1))
    left = contact_patch((box_triangles((-0.6, -1, -0.8), (-0.4, 0, 0.8)),), (cargo,), 0.0)
    right = contact_patch((box_triangles((0.4, -1, -0.8), (0.6, 0, 0.8)),), (cargo,), 0.0)
    assert support_margin((left, right), (0.0, 0.0)) == pytest.approx(0.6)
    with pytest.raises(MeshProofError, match="CoG"):
        support_margin((left, right), (0.7, 0.0))
