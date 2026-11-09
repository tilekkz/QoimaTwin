"""Continuous moving vehicle components relative to a source-seated body."""

from dataclasses import replace

from app.v3.mesh_proof_covers import covers, merge_covers
from app.v3.mesh_proof_geometry import empty_box
from app.v3.mesh_proof_motion import Pose, posed, select
from app.v3.mesh_proof_scene import RigidScene
from app.v3.pallet_operator_fit_geometry import NEUTRAL, vehicle_parts
from app.v3.pallet_outbound_pickup_geometry import mesh_segments
from app.v3.pallet_outbound_pickup_identity import require
from app.v3.pallet_outbound_pickup_models import PickupPlan


def check_component_interval(
    vehicle: RigidScene,
    person: RigidScene,
    start: Pose,
    end: Pose,
) -> int:
    # The source seated body follows the same root; only relative joint motion remains.
    start, end = replace(start, root_z=0.0), replace(end, root_z=0.0)
    first = select(vehicle, posed(vehicle, start, False), "joint__carriage")
    last = select(vehicle, posed(vehicle, end, False), "joint__carriage")
    require(bool(first) and bool(last) and bool(person.parts), "Moving/body geometry absent")
    hulls = merge_covers(covers(vehicle, first, start), covers(vehicle, last, end))
    body = tuple(p.triangles for p in person.world_parts())
    for hull in hulls:
        empty_box(body, hull.low, hull.high)
    return len(hulls)


def check_motion(
    vehicle: RigidScene,
    person: RigidScene,
    plan: PickupPlan,
) -> tuple[tuple[int, ...], int]:
    checks = tuple(
        check_component_interval(vehicle, person, s.start, s.end) for s in mesh_segments(plan)
    )
    wheels = tuple(
        p
        for p in vehicle_parts(vehicle)
        if any(n.startswith("joint__wheel_") for n in vehicle.lineage(p.node))
    )
    require(bool(wheels), "Actual source wheels absent")
    wheel_hulls = covers(vehicle, wheels, NEUTRAL)
    body = tuple(p.triangles for p in person.world_parts())
    for hull in wheel_hulls:
        empty_box(body, hull.low, hull.high)
    return checks, len(wheel_hulls)
