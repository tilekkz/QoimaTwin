"""Actual-mesh and independent padding counterexamples for one bounded arc."""

from dataclasses import replace
from fractions import Fraction as F
from typing import Any, cast

import pytest

from app.v3 import pallet_outbound_arc_verify as verification
from app.v3.mesh_proof_scene import RigidScene
from app.v3.pallet_outbound_arc_geometry import check_geometry
from app.v3.pallet_outbound_arc_models import ArcGeometry, ArcPlan
from app.v3.pallet_outbound_arc_obstacles import check_envelope, check_padding
from app.v3.pallet_outbound_arc_plan import compile_arc_plan, verify_arc_plan
from app.v3.pallet_outbound_pickup_geometry import source_scene
from app.v3.pallet_outbound_pickup_identity import identity
from app.v3.pallet_outbound_pickup_models import (
    PickupBounds,
    PickupCertificate,
    PickupPlan,
    PickupSource,
)
from tests.v3.test_pallet_outbound_arc_contract import pickup as pickup


@pytest.fixture(scope="module")
def arc(pickup: tuple[PickupSource, PickupPlan, PickupCertificate]) -> ArcPlan:
    return compile_arc_plan(*pickup)


def test_low_loaded_forks_have_actual_triangle_collision(
    pickup: tuple[PickupSource, PickupPlan, PickupCertificate],
    arc: ArcPlan,
) -> None:
    source, plan, _ = pickup
    wrong = replace(
        arc, start=replace(arc.start, fork_top=F(3, 10)), end=replace(arc.end, fork_top=F(3, 10))
    )
    with pytest.raises(ValueError, match="triangle intrusion"):
        check_geometry(source_scene(source, plan), source, plan, wrong)


def test_missing_fork_cannot_receive_a_contact_certificate(
    pickup: tuple[PickupSource, PickupPlan, PickupCertificate],
    arc: ArcPlan,
) -> None:
    source, plan, _ = pickup
    scene = source_scene(source, plan)
    missing = replace(
        scene, parts=tuple(p for p in scene.parts if "joint__fork_R" not in scene.lineage(p.node))
    )
    with pytest.raises(ValueError, match="support absent"):
        check_geometry(missing, source, plan, arc)


def test_axle_is_not_the_floor_root(
    pickup: tuple[PickupSource, PickupPlan, PickupCertificate],
    arc: ArcPlan,
) -> None:
    source, plan, _ = pickup
    wrong = replace(arc, axle_end_world=arc.root_end_world)
    with pytest.raises(ValueError, match="root/axle endpoint"):
        check_geometry(source_scene(source, plan), source, plan, wrong)


def test_positive_gap_still_fails_required_padding() -> None:
    box = PickupBounds((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
    obstacle = PickupBounds((1.2, 0.0, 0.0), (2.0, 1.0, 1.0))
    assert check_padding(box, (("obstacle", obstacle),), 0)[1] == pytest.approx(0.2)
    with pytest.raises(ValueError, match="padding"):
        check_padding(box, (("obstacle", obstacle),), 0.25)
    safe = PickupBounds((1.3, 0.0, 0.0), (2.0, 1.0, 1.0))
    assert check_padding(box, (("obstacle", safe),), 0.25)[1] == pytest.approx(0.3)


def test_top_padding_survives_an_unpadded_height_fit(arc: ArcPlan) -> None:
    box = PickupBounds((1.0, 0.0, 1.0), (2.0, 2.1, 2.0))
    envelope = PickupBounds((0.0, 0.0, 0.0), (10.0, 8.0, 10.0))
    with pytest.raises(ValueError, match="top padding"):
        check_envelope(box, envelope, replace(arc, clear_height_m=F(23, 10)))


def test_fraction_zero_alias_and_rehash_cannot_change_plan(
    pickup: tuple[PickupSource, PickupPlan, PickupCertificate],
    arc: ArcPlan,
) -> None:
    wrong = replace(arc, start=replace(arc.start, reach=cast(Any, False)), plan_hash="")
    wrong = replace(wrong, plan_hash=identity(wrong))
    with pytest.raises(ValueError):
        verify_arc_plan(*pickup, wrong)


def test_certificate_verify_recomputes_actual_geometry(
    pickup: tuple[PickupSource, PickupPlan, PickupCertificate],
    arc: ArcPlan,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    certificate = verification.certify_arc(*pickup, arc)
    observed: list[str] = []
    original = check_geometry

    def recompute(
        scene: RigidScene, source: PickupSource, plan: PickupPlan, route: ArcPlan
    ) -> ArcGeometry:
        observed.append(scene.sha256)
        return original(scene, source, plan, route)

    monkeypatch.setattr(verification, "check_geometry", recompute)
    verification.verify_arc_certificate(*pickup, arc, certificate)
    assert observed == [certificate.mesh_sha256]
