"""Small retained local authority, independent of the mutable stock/worker state."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, fields, is_dataclass
from fractions import Fraction
from typing import TYPE_CHECKING, Any

from app.storage.canonical_json import canonical_bytes
from app.v3.flow_profile_wire import record
from app.v3.pallet_cycle_types import CycleOperation, CycleTimingProfile, ExactPose
from app.v3.pallet_shared_models import PalletSharedJob, PalletSharedProfile

if TYPE_CHECKING:
    from app.v3.pallet_shared_engine import PalletSharedEngine


def binding_bytes(profile: PalletSharedProfile) -> bytes:
    return canonical_bytes(
        record(
            (
                profile.timing,
                profile.jobs,
                profile.hu_id,
                profile.platform_id,
                profile.vehicle_owner_id,
                profile.driver_anchor,
                profile.model_sha256,
                profile.inventory_scope,
                profile.initial_driver_state,
                profile.source_approach,
            )
        )
    )


def type_bytes(value: Any) -> bytes:
    """Save type structure independently; a retained mutable object is not its own reference."""
    return canonical_bytes(_type_shape(value))


def _type_shape(value: Any) -> Any:
    identity = type(value).__module__ + "." + type(value).__qualname__
    if is_dataclass(value) and not isinstance(value, type):
        return identity, tuple((f.name, _type_shape(getattr(value, f.name))) for f in fields(value))
    if isinstance(value, Mapping):
        return identity, tuple(
            (_type_shape(k), record(k), _type_shape(v))
            for k, v in sorted(value.items(), key=lambda row: str(row[0]))
        )
    if isinstance(value, (tuple, list)):
        return identity, tuple(_type_shape(v) for v in value)
    if isinstance(value, (set, frozenset)):
        return identity, tuple(sorted((_type_shape(v) for v in value), key=str))
    return identity


def _world(engine: PalletSharedEngine) -> None:
    world = engine.pallet_profile.world
    if (
        type_bytes(world) != engine.world_type_bytes
        or canonical_bytes(record(world)) != engine.world_bytes
    ):
        raise RuntimeError("PALLET retained world authority changed")


def _check_profile_types(profile: PalletSharedProfile) -> None:
    if (
        type(profile) is not PalletSharedProfile
        or type(profile.jobs) is not tuple
        or any(type(j) is not PalletSharedJob for j in profile.jobs)
        or type(profile.timing) is not CycleTimingProfile
        or any(
            type(v) is not Fraction
            for v in (
                profile.timing.root_speed_m_s,
                profile.timing.lift_speed_m_s,
                profile.timing.reach_speed_m_s,
                profile.timing.attach_s,
                profile.timing.release_s,
                profile.timing.hold_s,
            )
        )
    ):
        raise RuntimeError("PALLET retained typed authority changed")


def check_authority(engine: PalletSharedEngine) -> None:
    _world(engine)
    p = engine.pallet_profile
    _check_profile_types(p)
    if (
        p.world is not engine.whole_profile
        or binding_bytes(engine.pallet_profile) != engine.binding_bytes
        or canonical_bytes(record(engine.pallet_resources)) != engine.resource_bytes
        or canonical_bytes(record(engine.bridge)) != engine.bridge_bytes
    ):
        raise RuntimeError("PALLET retained local authority changed")
    specs = {j.job_id: j for j in engine.pallet_profile.jobs}
    if specs.keys() != engine.pallet_jobs.keys() or any(
        state.spec is not specs[key] for key, state in engine.pallet_jobs.items()
    ):
        raise RuntimeError("PALLET actual jobs differ from declared authority")
    if canonical_bytes(asdict(engine.proof)) != engine.proof_bytes:
        raise RuntimeError("PALLET retained proof changed")
    if type(engine.plan) is not tuple or canonical_bytes(record(engine.plan)) != engine.plan_bytes:
        raise RuntimeError("PALLET proved operation plan changed")
    for op in engine.plan:
        if (
            type(op) is not CycleOperation
            or type(op.ordinal) is not int
            or type(op.duration_ticks) is not int
            or op.duration_ticks <= 0
            or type(op.attached) is not bool
        ):
            raise RuntimeError("PALLET operation requires exact typed proof fields")
        check_pose(op.start_pose)
        check_pose(op.end_pose)
    check_pose(engine.vehicle.pose)
    current = engine.ledger.contents(engine.pallet_profile.hu_id)
    if canonical_bytes(record(tuple(u.token for u in current.units))) != engine.token_bytes:
        raise RuntimeError("PALLET original24 unit ancestry or recipe changed")
    if current.gross_mass_kg != 455 or len(current.units) != 24:
        raise RuntimeError("PALLET intact455kg physical identity changed")


def check_pose(pose: ExactPose) -> None:
    if type(pose) is not ExactPose or any(
        type(v) is not Fraction for v in (pose.root_z, pose.fork_top, pose.reach)
    ):
        raise RuntimeError("PALLET pose requires exact fractional coordinates")
