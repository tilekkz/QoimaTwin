"""Actual finite contacts, whole-body solid covers and seated source clearances."""

from typing import Any

import numpy as np

from app.v3.mesh_proof_contact import contact_patch
from app.v3.mesh_proof_geometry import empty_box
from app.v3.mesh_proof_motion import Pose, posed, select
from app.v3.mesh_proof_scene import RigidScene, Solid
from app.v3.mesh_proof_types import CONTACT_RESIDUAL_M, Array
from app.v3.pallet_operator_fit_models import OperatorAnchorFit, OperatorContact
from app.v3.pallet_outbound_pickup_frames import vector
from app.v3.pallet_outbound_pickup_identity import require
from app.v3.pallet_outbound_pickup_models import PickupBounds

NEUTRAL = Pose(0.0, 0.70, 0.0)


def vehicle_parts(scene: RigidScene) -> tuple[Solid, ...]:
    parts = select(scene, posed(scene, NEUTRAL, False), "forklift_root")
    require(bool(parts), "Actual vehicle geometry absent")
    return parts


def body_bounds(person: RigidScene) -> PickupBounds:
    require(bool(person.parts), "Actual body geometry absent")
    points = np.concatenate([p.triangles.reshape(-1, 3) for p in person.world_parts()])
    return PickupBounds(vector(points.min(axis=0)), vector(points.max(axis=0)))


def anchors(scene: RigidScene) -> dict[str, Array]:
    matrices = scene.matrices()
    return {
        n.name: matrices[i][:3, 3]
        for i, n in enumerate(scene.nodes)
        if n.name.startswith("anchor_")
    }


def check_anchors(
    person: RigidScene,
    vehicle: RigidScene,
    spec: dict[str, Any],
) -> tuple[OperatorAnchorFit, ...]:
    body, machine = anchors(person), anchors(vehicle)
    pairs = [("anchor_seat_contact", "anchor_driver_seat")]
    pairs += [("anchor_foot_floor_" + s, "anchor_footrest_" + s) for s in ("L", "R")]
    pairs += [("anchor_hand_grip_" + s, "anchor_steering_grip_" + s) for s in ("L", "R")]
    result = []
    for human, target in pairs:
        require(human in body and target in machine, "Actual source anchor absent")
        residual = float(np.max(np.abs(body[human] - machine[target])))
        declared = float(np.max(np.abs(machine[target] - spec["anchors"][target])))
        require(
            max(residual, declared) <= spec["driver"]["required_pose_tolerance_m"],
            "Actual source anchor mismatch: " + human,
        )
        result.append(OperatorAnchorFit(human, target, residual, declared))
    return tuple(result)


def matching_box(vehicle: RigidScene, spec: dict[str, Any], name: str) -> Solid:
    expected = next(box for box in spec["blueprint_boxes"] if box["name"] == name)
    matches = [
        p
        for p in vehicle_parts(vehicle)
        if np.allclose(
            p.triangles.min(axis=(0, 1)), expected["min"], atol=CONTACT_RESIDUAL_M, rtol=0
        )
        and np.allclose(
            p.triangles.max(axis=(0, 1)), expected["max"], atol=CONTACT_RESIDUAL_M, rtol=0
        )
    ]
    require(len(matches) == 1, "Actual source solid not uniquely bound: " + name)
    return matches[0]


def check_contacts(
    person: RigidScene,
    vehicle: RigidScene,
    spec: dict[str, Any],
) -> tuple[OperatorContact, ...]:
    parts = person.world_parts()
    pelvis = tuple(
        p.triangles
        for p in parts
        if (parent := person.nodes[p.node].parent) is not None
        and person.nodes[parent].name == "joint__pelvis"
    )
    require(bool(pelvis), "Actual pelvis geometry absent")
    seat = matching_box(vehicle, spec, "seat_cushion_rear")
    result = [
        OperatorContact(
            "seat",
            contact_patch((seat.triangles,), pelvis, spec["driver"]["seat_anchor_vehicle"][1]),
        )
    ]
    supports = tuple(p.triangles for p in vehicle_parts(vehicle))
    for side in ("L", "R"):
        boot = tuple(p.triangles for p in parts if "joint__foot_" + side in person.lineage(p.node))
        require(bool(boot), "Actual boot geometry absent")
        plane = spec["anchors"]["anchor_footrest_" + side][1]
        result.append(OperatorContact("boot_" + side, contact_patch(supports, boot, plane)))
    return tuple(result)


def check_body_clearance(person: RigidScene, obstacles: tuple[Solid, ...]) -> int:
    require(bool(person.parts) and bool(obstacles), "Body/vehicle solids required")
    matrices = person.matrices()
    for part in person.parts:
        frame = matrices[part.node]
        local = tuple((p.triangles - frame[:3, 3]) @ frame[:3, :3] for p in obstacles)
        empty_box(local, part.triangles.min(axis=(0, 1)), part.triangles.max(axis=(0, 1)))
    return len(person.parts)


def check_roof(person: RigidScene, vehicle: RigidScene, spec: dict[str, Any]) -> float:
    roof = matching_box(vehicle, spec, "roof_guard")
    gap = float(roof.triangles[:, :, 1].min() - body_bounds(person).high[1])
    require(gap >= spec["driver"]["minimum_helmet_roof_gap_m"], "Source minimum roof gap failed")
    return gap


def check_portal(person: RigidScene, spec: dict[str, Any]) -> PickupBounds:
    bounds, target = body_bounds(person), spec["driver"]["entry_clear_portal"]
    for axis, key in ((1, "y"), (2, "z")):
        require(
            bounds.low[axis] >= target[key][0] - CONTACT_RESIDUAL_M
            and bounds.high[axis] <= target[key][1] + CONTACT_RESIDUAL_M,
            "Seated body outside portal projection",
        )
    return bounds
