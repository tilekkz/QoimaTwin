"""Durations from declared metre coordinates and explicit synthetic rates."""

from fractions import Fraction as F
from pathlib import Path

import pytest

from app.v3.pallet_cycle_plan import build_cycle_plan, validate_timing
from app.v3.pallet_cycle_types import CycleTimingProfile

SOURCE = Path(__file__).resolve().parents[2] / "data" / "v3-mesh-proof-proposal"


def timing() -> CycleTimingProfile:
    return CycleTimingProfile(
        "hand-rates",
        F(1),
        F(13, 25),
        F(2, 5),
        F(1, 5),
        F(3, 10),
        F(1),
        "Explicit synthetic hand oracle",
    )


def test_declared_distances_produce_hand_cycle_times() -> None:
    plan = build_cycle_plan(SOURCE, timing())
    assert len(plan) == 15
    assert sum(op.duration_ticks for op in plan) == 13_700_000
    elapsed = 0
    handovers: dict[str, int] = {}
    for operation in plan:
        assert operation.duration_ticks > 0
        elapsed += operation.duration_ticks
        if operation.kind in ("attach", "release"):
            handovers[operation.kind] = elapsed
    assert handovers == {"attach": 3_250_000, "release": 10_650_000}


def test_original_decimal_difference_is_not_a_binary_float_subtraction() -> None:
    plan = build_cycle_plan(SOURCE, timing())
    lower = next(op for op in plan if op.phase == "lower_extended")
    assert lower.start_pose.fork_top - lower.end_pose.fork_top == F(13, 25)
    assert lower.duration_ticks == 1_000_000


def test_each_positive_operation_is_ceiled_separately() -> None:
    from dataclasses import replace

    profile = replace(timing(), root_speed_m_s=F(3), lift_speed_m_s=F(3), reach_speed_m_s=F(3))
    plan = build_cycle_plan(SOURCE, profile)
    # 4*350000 + 4*ceil(520000/3) + 4*ceil(400000/3) + 1500000.
    assert sum(op.duration_ticks for op in plan) == 4_126_672


@pytest.mark.parametrize("invalid", [F(0), F(-1), True, float("nan")])
def test_nonpositive_or_inexact_rate_is_rejected(invalid: object) -> None:
    from dataclasses import replace
    from typing import cast

    with pytest.raises(ValueError):
        build_cycle_plan(SOURCE, replace(timing(), root_speed_m_s=cast(F, invalid)))


@pytest.mark.parametrize("field", ["profile_id", "provenance_note"])
def test_timing_identity_and_provenance_are_explicit_text(field: str) -> None:
    from dataclasses import replace
    from typing import cast

    profile = (
        replace(timing(), profile_id=cast(str, True))
        if field == "profile_id"
        else replace(timing(), provenance_note=cast(str, True))
    )
    with pytest.raises(ValueError, match=r"identity|provenance"):
        validate_timing(profile)
