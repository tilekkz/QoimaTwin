"""Physical counterexamples retained from the independent external V5 packet."""

import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from app.v3.mesh_proof_motion import Pose, Segment, validate_motion
from app.v3.mesh_proof_scene import RigidScene
from app.v3.mesh_proof_types import MeshProofError
from app.v3.pallet_outbound_pickup_geometry import (
    check_source_frame,
    check_sweeps,
    contacts_at,
    mesh_segments,
    source_scene,
)
from app.v3.pallet_outbound_pickup_models import PickupPlan
from app.v3.pallet_outbound_pickup_obstacles import check_obstacles
from app.v3.pallet_outbound_pickup_plan import compile_pickup_plan
from app.v3.pallet_outbound_pickup_source import load_pickup_source

DATA = Path(__file__).resolve().parents[2] / "data"


@pytest.fixture(scope="module")
def geometry() -> tuple[RigidScene, PickupPlan, tuple[Segment, ...]]:
    source = load_pickup_source(DATA)
    plan = compile_pickup_plan(source)
    return source_scene(source, plan), plan, mesh_segments(plan)


def shifted(scene: RigidScene, name: str, offset: tuple[float, float, float]) -> RigidScene:
    nodes = []
    for node in scene.nodes:
        matrix = node.matrix.copy()
        if node.name == name:
            matrix[:3, 3] += offset
        nodes.append(replace(node, matrix=matrix))
    return replace(scene, nodes=tuple(nodes))


def test_inward_one_mm_rejects_actual_triangle_intrusion(
    geometry: tuple[RigidScene, PickupPlan, tuple[Segment, ...]],
) -> None:
    scene, _, _ = geometry
    segment = Segment(1, "inward_lower", Pose(-0.999, 0.7, 0.4), Pose(-0.999, 0.18, 0.4), False)
    with pytest.raises(MeshProofError, match="triangle intrusion"):
        check_sweeps(scene, (segment,))


def test_low_loaded_travel_rejects_actual_vehicle_intrusion(
    geometry: tuple[RigidScene, PickupPlan, tuple[Segment, ...]],
) -> None:
    scene, _, _ = geometry
    segment = Segment(0, "low_travel", Pose(0, 0.3, 0), Pose(-1, 0.3, 0), True)
    with pytest.raises(MeshProofError, match="triangle intrusion"):
        check_sweeps(scene, (segment,))


def test_shifted_platform_blocks_actual_lane(
    geometry: tuple[RigidScene, PickupPlan, tuple[Segment, ...]],
) -> None:
    scene, _, segments = geometry
    blocked = shifted(scene, "heavy-bay__MODULE", (0.2, 0, 0))
    with pytest.raises(MeshProofError, match="triangle intrusion"):
        check_sweeps(blocked, (segments[2],))


def test_raised_support_has_no_finite_matching_patch(
    geometry: tuple[RigidScene, PickupPlan, tuple[Segment, ...]],
) -> None:
    scene, _, segments = geometry
    raised = shifted(scene, "heavy-bay__MODULE", (0, 0.01, 0))
    with pytest.raises(MeshProofError, match="no finite"):
        contacts_at(raised, segments[0].start, 0, ("heavy-bay__MODULE",))


def test_missing_fork_cannot_be_replaced_by_other_support(
    geometry: tuple[RigidScene, PickupPlan, tuple[Segment, ...]],
) -> None:
    scene, _, segments = geometry
    with pytest.raises(ValueError, match="support absent"):
        contacts_at(scene, segments[-1].end, 6, ("joint__fork_L", "missing"))


def test_attachment_cannot_jump_five_cm(
    geometry: tuple[RigidScene, PickupPlan, tuple[Segment, ...]],
) -> None:
    _, _, segments = geometry
    with pytest.raises(MeshProofError, match="continuous"):
        validate_motion((segments[2], replace(segments[3], start=Pose(0.05, 0.18, 0.4))))


def test_old_fixture_hu_heading_is_not_source_orientation(
    geometry: tuple[RigidScene, PickupPlan, tuple[Segment, ...]],
) -> None:
    scene, plan, _ = geometry
    nodes = []
    for node in scene.nodes:
        matrix = node.matrix.copy()
        if node.name == "pallet-load__HU":
            matrix[:3, :3] = np.eye(3)
        nodes.append(replace(node, matrix=matrix))
    with pytest.raises(ValueError, match="signed axes"):
        check_source_frame(replace(scene, nodes=tuple(nodes)), plan)


def test_action_expanded_into_neighbor_rejects() -> None:
    from app.v3.pallet_outbound_pickup_models import PickupBounds

    source = load_pickup_source(DATA)
    plan = compile_pickup_plan(source)
    with pytest.raises(ValueError, match="module intersects"):
        check_obstacles(source, plan, PickupBounds((121.7, 0, 28.2), (126.4, 2.1, 30.3)))


def test_public_import_has_no_engine_scheduler_or_ledger_dependencies() -> None:
    code = (
        "import sys; import app.v3.pallet_outbound_pickup_verify; "
        "bad=[m for m in sys.modules if m=='simpy' or m.startswith('app.v3.coordinator') "
        "or m.startswith('app.v3.pallet_shared') or m=='app.v3.stock_ledger']; "
        "assert not bad, bad"
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", code],
        check=False,
        capture_output=True,
        text=True,
        cwd=DATA.parent,
    )
    assert result.returncode == 0, result.stderr
