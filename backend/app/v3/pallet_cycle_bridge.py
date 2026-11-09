"""Two separately directed, source-bound and newly swept local 5cm connections."""

import math
from dataclasses import replace
from fractions import Fraction as F
from pathlib import Path

import numpy as np

from app.v3.mesh_proof_motion import Pose, Segment
from app.v3.mesh_proof_source import load_fixture
from app.v3.mesh_proof_sweeps import verify_segment
from app.v3.pallet_cycle_types import (
    DRIVER_ID,
    PLATFORM_ID,
    VEHICLE_ID,
    CycleBridge,
    CycleOperation,
    CycleTimingProfile,
    ExactPose,
)
from app.v3.runtime_time import travel_ticks
from app.v3.vehicle_package import load_repository_vehicle_adapter
from app.v3.vehicle_source import VehicleAdapter
from app.v3.vehicle_types import VehicleArc

ARC_PREFIX = "v3:module:HEAVY_E:001:B1:vehicle:segment:002:"
PAIR_ID = "INBOUND_FORKLIFT_PAIR"
FIXTURE_ORIGIN_X = F(599, 5)


def _permitted_arc(adapter: VehicleAdapter, direction: str) -> VehicleArc:
    arc = adapter.graph.arcs.get(ARC_PREFIX + direction)
    if arc is None:
        raise ValueError("both explicit directed bridge arcs are required")
    if (
        PAIR_ID not in arc.equipment_pairs
        or (PAIR_ID, DRIVER_ID, VEHICLE_ID) not in adapter.handling.pairs
    ):
        raise ValueError("bridge arc lacks the fixed F01/FL01 pair permission")
    if "nonlong_forklift" not in arc.profiles or "PALLET_LOAD" not in arc.cargo_classes:
        raise ValueError("bridge arc lacks the declared PALLET handling profile")
    geometry = arc.geometry
    yaw_error = math.remainder(float(geometry.start_yaw_rad) + math.pi / 2, 2 * math.pi)
    if (
        geometry.kind != "line"
        or geometry.start_yaw_rad != geometry.end_yaw_rad
        or abs(yaw_error) > 1e-12
        or arc.rear_steer_deg != 0
    ):
        raise ValueError("only the fixed straight local bridge geometry is proved")
    if arc.motion_direction != (-1 if direction == "r" else 1):
        raise ValueError("bridge direction disagrees with source physical yaw")
    return arc


def validate_bridge_source(adapter: VehicleAdapter) -> CycleBridge:
    entry, exit_arc = _permitted_arc(adapter, "r"), _permitted_arc(adapter, "f")
    if entry.source != exit_arc.target or entry.target != exit_arc.source:
        raise ValueError("directed bridge endpoints do not agree")
    start = adapter.graph.nodes[entry.source].root_xyz
    end = adapter.graph.nodes[entry.target].root_xyz
    action = (F(2417, 20), F(0), F(35, 2))
    if start != (F(604, 5), F(0), F(35, 2)) or end[1:] != start[1:] or end[0] <= action[0]:
        raise ValueError("bridge does not lie in the fixed declared source segment")
    distance = action[0] - start[0]
    progress = distance / (end[0] - start[0])
    slot = next((s for s in adapter.handling.slots if s.slot_id == PLATFORM_ID), None)
    if (
        slot is None
        or slot.blocked
        or slot.vehicle_node_id != entry.source
        or slot.support_y_m != F(9, 50)
        or slot.max_payload_kg < 455
        or "PALLET_LOAD" not in slot.cargo_classes
    ):
        raise ValueError("source platform does not permit this local PALLET support")
    resources = tuple(sorted(set(entry.traffic_groups) | set(exit_arc.traffic_groups)))
    if any(adapter.graph.resources[key].capacity != 1 for key in resources):
        raise ValueError("bridge traffic resources must be exclusive")
    return CycleBridge(
        adapter.source_revision,
        adapter.source_hashes,
        entry.arc_id,
        exit_arc.arc_id,
        start,
        action,
        distance,
        (F(0), progress),
        (1 - progress, F(1)),
        resources,
    )


def _pose(value: ExactPose) -> Pose:
    return Pose(float(value.root_z), float(value.fork_top), float(value.reach))


def build_bridges(
    proof_root: Path,
    profile: CycleTimingProfile,
    start_pose: ExactPose,
    base_root: Path,
    vehicle_root: Path,
) -> tuple[CycleOperation, CycleOperation, CycleBridge]:
    adapter = load_repository_vehicle_adapter(base_root, vehicle_root)
    binding = validate_bridge_source(adapter)
    expected = ExactPose(FIXTURE_ORIGIN_X - binding.action_start_xyz[0], F(7, 10), F(0))
    if start_pose != expected:
        raise ValueError("proved fixture action start disagrees with the source bridge")
    before = ExactPose(
        FIXTURE_ORIGIN_X - binding.prehandle_xyz[0], start_pose.fork_top, start_pose.reach
    )
    duration = travel_ticks(binding.distance_m, profile.root_speed_m_s)
    entry = CycleOperation(
        0, "bridge", "source_approach", duration, before, start_pose, False, binding.entry_arc_id
    )
    exit_op = CycleOperation(
        0, "bridge", "source_return", duration, start_pose, before, False, binding.exit_arc_id
    )
    fixture = load_fixture(proof_root)
    bounds = np.array([-0.8, 0.0, -2.55]), np.array([0.8, 2.1, 2.2])
    checked = tuple(
        verify_segment(
            fixture.scene,
            Segment(i, op.phase, _pose(op.start_pose), _pose(op.end_pose), False),
            bounds,
        )
        for i, op in enumerate((entry, exit_op))
    )
    return (
        entry,
        exit_op,
        replace(binding, entry_cover_checks=checked[0], exit_cover_checks=checked[1]),
    )
