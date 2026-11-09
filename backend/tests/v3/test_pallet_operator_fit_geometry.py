"""Hand geometry and deliberate actual-mesh perturbations, without runtime."""

import math

import numpy as np
import pytest

from app.v3.mesh_proof_geometry import inside_solid
from app.v3.mesh_proof_motion import Pose
from app.v3.mesh_proof_scene import RigidScene
from app.v3.pallet_operator_fit_geometry import (
    check_anchors,
    check_body_clearance,
    check_contacts,
    check_portal,
    check_roof,
    matching_box,
    vehicle_parts,
)
from app.v3.pallet_operator_fit_motion import check_component_interval
from app.v3.pallet_operator_fit_pose import euler_xyz, fit_scenes
from app.v3.pallet_operator_fit_source import forklift_spec
from tests.v3.test_pallet_operator_fit_fixtures import box_scene, shifted, source


def test_hand_touching_boxes_clear_but_one_mm_intrusion_rejects() -> None:
    body = box_scene()
    vehicle = shifted(box_scene(), "body", (0.2, 0, 0))
    assert check_body_clearance(body, vehicle.world_parts()) == 1
    vehicle = shifted(vehicle, "body", (-0.001, 0, 0))
    with pytest.raises(ValueError):
        check_body_clearance(body, vehicle.world_parts())


def test_hand_midinterval_collision_cannot_hide_at_clear_endpoints() -> None:
    vehicle = box_scene(moving=True)
    body = shifted(box_scene(), "body", (0, 1.5, 0))
    start, end = Pose(0, 0, 0), Pose(0, 3, 0)
    assert check_component_interval(vehicle, body, start, start) == 1
    assert check_component_interval(vehicle, body, end, end) == 1
    with pytest.raises(ValueError):
        check_component_interval(vehicle, body, start, end)


@pytest.fixture(scope="module")
def actual() -> tuple[RigidScene, RigidScene]:
    return fit_scenes(source())


def test_source_pose_keeps_exact_finite_seat_and_two_boot_supports(
    actual: tuple[RigidScene, RigidScene],
) -> None:
    worker, vehicle = actual
    contacts = check_contacts(worker, vehicle, forklift_spec(source()))
    assert tuple(c.support for c in contacts) == ("seat", "boot_L", "boot_R")
    assert all(c.patch.area_m2 > 0.02 for c in contacts)
    assert all(c.patch.maximum_gap_m < 0.000002 for c in contacts)


@pytest.mark.parametrize("height", [0.002, -0.001])
def test_floating_or_penetrating_body_loses_seat_support(
    actual: tuple[RigidScene, RigidScene],
    height: float,
) -> None:
    worker, vehicle = actual
    worker = shifted(worker, "worker_base_root", (0, height, 0))
    with pytest.raises(ValueError):
        check_contacts(worker, vehicle, forklift_spec(source()))


def test_raised_right_boot_has_no_support(actual: tuple[RigidScene, RigidScene]) -> None:
    worker, vehicle = actual
    worker = shifted(worker, "joint__foot_R", (0, 0.002, 0))
    with pytest.raises(ValueError):
        check_contacts(worker, vehicle, forklift_spec(source()))


def test_source_helmet_height_leaves_five_cm_not_four_point_four(
    actual: tuple[RigidScene, RigidScene],
) -> None:
    worker, vehicle = actual
    spec = forklift_spec(source())
    assert check_roof(worker, vehicle, spec) == pytest.approx(2.04 - 1.99, abs=2e-6)
    with pytest.raises(ValueError, match="roof"):
        check_roof(shifted(worker, "worker_base_root", (0, 0.006, 0)), vehicle, spec)


def test_forward_body_breaks_actual_grip_anchors(actual: tuple[RigidScene, RigidScene]) -> None:
    worker, vehicle = actual
    with pytest.raises(ValueError, match="anchor"):
        check_anchors(
            shifted(worker, "worker_base_root", (0, 0, 0.1)), vehicle, forklift_spec(source())
        )


def test_seated_portal_projection_does_not_allow_backward_body(
    actual: tuple[RigidScene, RigidScene],
) -> None:
    worker, _ = actual
    with pytest.raises(ValueError, match="portal"):
        check_portal(shifted(worker, "worker_base_root", (0, 0, -0.3)), forklift_spec(source()))


def test_intrinsic_xyz_hand_rotation_order() -> None:
    # Apply local Y quarter-turn, then world X quarter-turn: X -> -Z -> +Y.
    result = euler_xyz([math.pi / 2, math.pi / 2, 0]) @ np.array([1.0, 0.0, 0.0])
    assert result == pytest.approx((0, 1, 0), abs=1e-15)


def test_lowered_body_has_concrete_shared_interior_witness(
    actual: tuple[RigidScene, RigidScene],
) -> None:
    worker, vehicle = actual
    worker = shifted(worker, "worker_base_root", (0, -0.001, 0))
    witness = np.array([0, 0.8395, -0.6915])
    seat = matching_box(vehicle, forklift_spec(source()), "seat_cushion_rear")
    assert inside_solid(seat.triangles, witness)
    assert any(
        inside_solid(part.triangles, witness)
        for part in worker.world_parts()
        if "joint__pelvis" in worker.lineage(part.node)
    )
    with pytest.raises(ValueError):
        check_body_clearance(worker, vehicle_parts(vehicle))
