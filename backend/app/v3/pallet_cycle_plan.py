"""Exact declared-coordinate arithmetic; visual timestamps never set durations."""

import hashlib
import json
from decimal import Decimal
from fractions import Fraction
from itertools import pairwise
from pathlib import Path
from typing import Any, Literal

from app.v3.mesh_proof_source import ACTION_PATH, load_fixture
from app.v3.pallet_cycle_types import CycleOperation, CycleTimingProfile, ExactPose
from app.v3.runtime_time import operation_ticks


def validate_timing(profile: CycleTimingProfile) -> None:
    values = (
        profile.root_speed_m_s,
        profile.lift_speed_m_s,
        profile.reach_speed_m_s,
        profile.attach_s,
        profile.release_s,
        profile.hold_s,
    )
    if any(type(value) is not Fraction or value <= 0 for value in values):
        raise ValueError("timing parameters must be positive exact Fractions")
    if any(
        not isinstance(value, str) or not value.strip()
        for value in (profile.profile_id, profile.provenance_note)
    ):
        raise ValueError("explicit timing identity and provenance are required")
    if profile.source_kind != "synthetic" or profile.driver_initial_state != "seated_in_FL01":
        raise ValueError("only explicit synthetic rates and seated F01/FL01 are supported")


def _pose(key: dict[str, Any]) -> ExactPose:
    return ExactPose(Fraction(key["root_z"]), Fraction(key["fork_top"]), Fraction(key["reach"]))


def _motion_duration(start: ExactPose, end: ExactPose, profile: CycleTimingProfile) -> int:
    seconds = max(
        abs(end.root_z - start.root_z) / profile.root_speed_m_s,
        abs(end.fork_top - start.fork_top) / profile.lift_speed_m_s,
        abs(end.reach - start.reach) / profile.reach_speed_m_s,
    )
    return operation_ticks(seconds if seconds else profile.hold_s)


def _operations(
    keys: list[dict[str, Any]], profile: CycleTimingProfile
) -> tuple[CycleOperation, ...]:
    result: list[CycleOperation] = []
    previous_attached = False
    for first, second in pairwise(keys):
        start, end = _pose(first), _pose(second)
        attached = first["attached"]
        if attached != previous_attached:
            kind: Literal["attach", "release"] = "attach" if attached else "release"
            delay = profile.attach_s if attached else profile.release_s
            result.append(
                CycleOperation(
                    len(result), kind, kind, operation_ticks(delay), start, start, previous_attached
                )
            )
        result.append(
            CycleOperation(
                len(result),
                "hold" if start == end else "motion",
                first["phase"],
                _motion_duration(start, end, profile),
                start,
                end,
                attached,
            )
        )
        previous_attached = attached
    return tuple(result)


def build_cycle_plan(proof_root: Path, profile: CycleTimingProfile) -> tuple[CycleOperation, ...]:
    """Compile timing only; a plan alone does not authorize execution."""
    validate_timing(profile)
    fixture = load_fixture(proof_root)
    raw = (proof_root / ACTION_PATH).read_bytes()
    if hashlib.sha256(raw).hexdigest() != dict(fixture.hashes)[ACTION_PATH]:
        raise ValueError("source action changed before timing compilation")
    document = json.loads(raw, parse_float=Decimal)
    return _operations(document["keys"], profile)
