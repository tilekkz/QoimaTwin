"""Finite area and quasi-static CoG oracles independent of source proof output."""

from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

from app.v3.mesh_proof_contact import contact_patch, support_margin
from app.v3.mesh_proof_motion import Pose, posed, select, translations
from app.v3.mesh_proof_source import Fixture, load_fixture
from app.v3.mesh_proof_types import CONTACT_RESIDUAL_M, MeshProofError
from tests.v3.test_mesh_independent_geometry import cuboid


@lru_cache(maxsize=1)
def fixture() -> Fixture:
    return load_fixture(Path("data/v3-mesh-proof-proposal"))


def test_separated_supports_have_exact_union_area_and_combined_hull_margin() -> None:
    cargo = cuboid((-2.0, 0.0, -1.0), (2.0, 1.0, 1.0))
    supports = (
        cuboid((-1.5, -1.0, -0.5), (-0.5, 0.0, 0.5)),
        cuboid((0.5, -1.0, -0.5), (1.5, 0.0, 0.5)),
    )
    patches = tuple(contact_patch((solid,), (cargo,), 0.0) for solid in supports)
    assert [p.area_m2 for p in patches] == pytest.approx([1.0, 1.0], abs=1e-14)
    np.testing.assert_allclose(
        [p.centroid_xz for p in patches], [(-1.0, 0.0), (1.0, 0.0)], atol=1e-14, rtol=0
    )
    # CoG over the gap is supported by opposite vertical reaction forces.
    assert support_margin(patches, (0.0, 0.0)) == pytest.approx(0.5)
    for cog in ((1.5, 0.0), (0.0, 0.5), (0.0, 0.6)):
        with pytest.raises(MeshProofError, match="CoG"):
            support_margin(patches, cog)


@pytest.mark.parametrize("offset", [(1.0, 0.0), (1.0, 1.0)])
def test_edge_and_vertex_only_touch_supply_no_finite_support(offset: tuple[float, float]) -> None:
    support = cuboid((0.0, -1.0, 0.0), (1.0, 0.0, 1.0))
    x, z = offset
    cargo = cuboid((x, 0.0, z), (x + 1, 1.0, z + 1))
    with pytest.raises(MeshProofError, match="contact area"):
        contact_patch((support,), (cargo,), 0.0)


def test_opposing_residuals_cannot_double_the_permitted_contact_gap() -> None:
    residual = CONTACT_RESIDUAL_M
    support = cuboid((0.0, -1.0, 0.0), (1.0, -0.75 * residual, 1.0))
    cargo = cuboid((0.0, 0.75 * residual, 0.0), (1.0, 1.0, 1.0))
    # Each plane is close to the nominal plane, but the actual gap is1.5*limit.
    with pytest.raises(MeshProofError, match="contact area"):
        contact_patch((support,), (cargo,), 0.0)


def test_actual_mesh_attach_keeps_same_hu_geometry_and_declared_cog_projection() -> None:
    scene, pose = fixture().scene, Pose(0.0, 0.18, 0.4)
    before = select(scene, posed(scene, pose, False), "pallet-load__HU")
    after = select(scene, posed(scene, pose, True), "pallet-load__HU")
    assert len(before) == len(after) > 0
    for old, new in zip(before, after, strict=True):
        assert (old.node, old.name) == (new.node, new.name)
        np.testing.assert_allclose(old.triangles, new.triangles, atol=2e-6, rtol=0)
        assert not old.triangles.flags.writeable and not new.triangles.flags.writeable
    matrices = scene.matrices(translations(pose, True))
    index = next(i for i, node in enumerate(scene.nodes) if node.name == "anchor_cog_declared")
    np.testing.assert_allclose(matrices[index][:3, 3], [0.0, 0.855, 1.4], atol=2e-6, rtol=0)


def test_actual_fork_patches_are_finite_bounded_by_declared_blade_board_area() -> None:
    scene, pose = fixture().scene, Pose(0.0, 0.18, 0.4)
    parts = posed(scene, pose, True)
    cargo = tuple(p.triangles for p in select(scene, parts, "pallet-load__HU"))
    patches = tuple(
        contact_patch(tuple(p.triangles for p in select(scene, parts, name)), cargo, 0.18)
        for name in ("joint__fork_L", "joint__fork_R")
    )
    # Source width.08 intersects3 bottom boards of depth.20 each; bevels can only remove area.
    upper = (0.08 + 2 * CONTACT_RESIDUAL_M) * (0.6 + 6 * CONTACT_RESIDUAL_M)
    assert all(0 < patch.area_m2 <= upper for patch in patches)
    assert all(patch.maximum_gap_m <= CONTACT_RESIDUAL_M for patch in patches)
    assert 0 < support_margin(patches, (0.0, 1.4)) < 0.5
