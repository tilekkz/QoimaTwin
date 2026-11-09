"""Loaded endpoint component bounds and first-arc pose seam, not a route proof."""

import numpy as np

from app.v3.mesh_proof_covers import Cover, covers
from app.v3.mesh_proof_motion import Pose, posed, select
from app.v3.mesh_proof_scene import RigidScene
from app.v3.pallet_outbound_pickup_frames import cover_bounds, ry, vector, world_box, world_point
from app.v3.pallet_outbound_pickup_identity import require
from app.v3.pallet_outbound_pickup_models import PickupBounds, PickupPlan, PickupSource, Vec3
from app.v3.pallet_outbound_pickup_plan import selected


def check_endpoint(
    scene: RigidScene, source: PickupSource, plan: PickupPlan, pose: Pose
) -> tuple[PickupBounds, PickupBounds, Vec3, Vec3, str]:
    facts = selected(source)
    parts = posed(scene, pose, True)
    groups = [select(scene, parts, name) for name in ("forklift_root", "pallet-load__HU")]
    collected: list[Cover] = []
    for group, bound in zip(groups, facts["load"]["component_bounds_local_m"], strict=True):
        hulls = covers(scene, group, pose)
        low, high = cover_bounds(hulls)
        offset = np.array([0, 0, pose.root_z])
        require(
            bool(
                np.all(low - offset >= np.array(bound["min"]) - 2e-6)
                and np.all(high - offset <= np.array(bound["max"]) + 2e-6)
            ),
            "Loaded endpoint exceeds C08 component envelope",
        )
        collected.extend(hulls)
    full = world_box(plan, *cover_bounds(collected))
    cargo = np.concatenate([p.triangles for p in groups[1]])
    hu_box = world_box(plan, cargo.min(axis=(0, 1)), cargo.max(axis=(0, 1)))
    root = world_point(plan, np.array([0, 0, pose.root_z]))
    axle = vector(np.array(root) + ry(plan.frame_yaw_rad) @ np.array([0, 0, 0.4]))
    arc = facts["arc"]
    require(
        np.allclose(root, plan.source_root_world, atol=2e-6, rtol=0)
        and np.allclose(
            np.array(axle)[[0, 2]], arc["geometry"]["front_axle_start_xz_m"], atol=2e-6, rtol=0
        ),
        "Loaded endpoint misses source first-arc seam",
    )
    require(
        arc["geometry"]["start_yaw_rad"] == plan.source_yaw_rad and arc["motion_direction"] == -1,
        "First-arc yaw/direction differs",
    )
    return full, hu_box, root, axle, str(arc["arc_id"])
