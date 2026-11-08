"""Type-preserving one-HU ownership; no mesh execution or engine-derived oracle."""

from dataclasses import replace
from fractions import Fraction as F
from typing import cast

import pytest

from app.v3.pallet_cycle_state import CycleInvariantError, CycleState, check_state, resource_ids
from app.v3.pallet_cycle_types import (
    ActiveOperation,
    CycleJob,
    CycleJobView,
    CycleLease,
    CycleOperation,
    ExactPose,
    PhysicalPallet,
)


def _state(*, active: bool = False) -> CycleState:
    hu = PhysicalPallet("HU", "PALLET_LOAD", 24, F(455), "a" * 64)
    pose = ExactPose(F(0), F(0), F(0))
    state = CycleState(hu, (CycleJob("job", 0, "HU"),), pose)
    if active:
        state.jobs["job"] = CycleJobView("job", "active")
        state.active_job = "job"
        state.active = ActiveOperation(
            "job", CycleOperation(0, "hold", "hand-hold", 10, pose, pose, False), 0, 10
        )
        state.leases = {r: CycleLease(r, "job", 0) for r in resource_ids("HU")}
    return state


def test_exact_idle_and_owned_state_are_valid() -> None:
    check_state(_state(), resource_ids("HU"), 0)
    check_state(_state(active=True), resource_ids("HU"), 2)


@pytest.mark.parametrize("field", ["units", "gross_mass_kg"])
def test_value_equal_numeric_substitution_cannot_replace_physical_hu(field: str) -> None:
    state = _state()
    state.hu = (
        replace(state.hu, units=cast(int, F(24)))
        if field == "units"
        else replace(state.hu, gross_mass_kg=cast(F, 455))
    )
    with pytest.raises(CycleInvariantError):
        check_state(state, resource_ids("HU"), 0)


def test_boolean_acquisition_time_cannot_pass_as_integer_one() -> None:
    state = _state(active=True)
    lease = state.leases["worker:F01"]
    state.leases["worker:F01"] = replace(lease, acquired_tick=True)
    with pytest.raises(CycleInvariantError):
        check_state(state, resource_ids("HU"), 2)
