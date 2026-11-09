"""Reuse proved geometry and timing only, never the standalone component scheduler/state."""

from dataclasses import replace
from pathlib import Path

from app.v3.pallet_cycle_bridge import build_bridges
from app.v3.pallet_cycle_plan import build_cycle_plan
from app.v3.pallet_cycle_types import CycleBridge, CycleOperation
from app.v3.pallet_shared_models import PalletSharedProfile


def shared_plan(
    profile: PalletSharedProfile,
    proof_root: Path,
) -> tuple[tuple[CycleOperation, ...], CycleBridge | None]:
    plan = build_cycle_plan(proof_root, profile.timing)
    if not profile.source_approach:
        return plan, None
    data = Path(__file__).resolve().parents[2] / "data"
    entry, exit_op, bridge = build_bridges(
        proof_root,
        profile.timing,
        plan[0].start_pose,
        data / "v3-proposal",
        data / "v3-vehicle-proposal",
    )
    return tuple(replace(op, ordinal=i) for i, op in enumerate((entry, *plan, exit_op))), bridge


def resource_ids(profile: PalletSharedProfile, bridge: CycleBridge | None) -> tuple[str, ...]:
    resources = {
        "worker:F01",
        "vehicle:FL01",
        "slot:" + profile.platform_id,
        "hu:" + profile.hu_id,
        "action_space:" + profile.platform_id + ":pallet_cycle",
    }
    if bridge is not None:
        resources.update(bridge.resource_ids)
    return tuple(sorted(resources))
