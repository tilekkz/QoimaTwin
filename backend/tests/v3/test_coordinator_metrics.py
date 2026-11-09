"""Independent staffing arithmetic; written before metrics, execution deferred to final gate."""

from dataclasses import replace
from functools import cache
from typing import cast

import pytest

from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.coordinator_metrics import summary
from app.v3.coordinator_models import CoordinatorOutcome, CoordinatorProfile
from tests.v3.test_coordinator_fixtures import staffing_profile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor


@cache
def role_case(horizon: int) -> tuple[CoordinatorProfile, CoordinatorOutcome]:
    profile = staffing_profile()
    return profile, CoordinatorEngine(profile, receipt_conveyor()).run(horizon, horizon)


def test_role_assignment_time_is_distinct_from_paid_worker_operations() -> None:
    profile, outcome = role_case(200 * SECOND)
    metrics = summary(profile, outcome)
    observed = metrics["at_horizon"]
    assert observed["role_assignment"]["role_ticks"]["pack"] == 1180 * SECOND
    assert observed["role_assignment"]["transition_ticks"] == 20 * SECOND
    assert observed["role_assignment"]["unavailable_ticks"] == 120 * SECOND
    assert observed["labor"]["paid_ticks"] == 20 * SECOND
    assert observed["labor"]["role_transition_paid_ticks"] == 20 * SECOND
    assert observed["labor"]["roster_paid_fraction"] == {"numerator": 1, "denominator": 240}
    assert observed["labor"]["available_roster_paid_fraction"] == {
        "numerator": 1,
        "denominator": 234,
    }
    assert observed["labor"]["paid_ticks_by_effective_role"]["transition"] == 20 * SECOND
    assert observed["labor"]["role_paid_fraction"]["pack"] == {"numerator": 0, "denominator": 1}
    assert metrics["completion"] == {
        "business_complete_tick": 0,
        "resource_drained_tick": 160 * SECOND,
        "observation_end_tick": 200 * SECOND,
        "staffing_status": "valid",
        "constraint_violations": [],
    }


def test_open_role_operation_charges_only_observed_half_open_interval() -> None:
    profile, outcome = role_case(105 * SECOND)
    result = summary(profile, outcome)
    observed = result["at_horizon"]
    assert observed["role_assignment"]["role_ticks"]["pack"] == 621 * SECOND
    assert observed["labor"]["paid_ticks"] == 9 * SECOND
    assert observed["labor"]["role_transition_paid_ticks"] == 9 * SECOND
    assert result["completion"]["resource_drained_tick"] is None
    assert result["integral_window"] == "[0,T)"
    assert result["counts_boundary"] == "settled_tick_inclusive"


def test_boolean_numeric_equal_labor_counter_is_rejected() -> None:
    profile, outcome = role_case(105 * SECOND)
    workers = list(outcome.at_horizon.workers)
    workers[0] = replace(workers[0], paid_ticks=cast(int, True))
    wrong = replace(outcome.at_horizon, workers=tuple(workers))
    with pytest.raises(ValueError, match="integer"):
        summary(profile, replace(outcome, at_horizon=wrong))


def test_assignment_exposure_cannot_lose_a_worker_second() -> None:
    profile, outcome = role_case(200 * SECOND)
    exposure = replace(outcome.at_horizon.exposure, transition_ticks=19 * SECOND)
    with pytest.raises(ValueError, match=r"24|exposure"):
        summary(
            profile, replace(outcome, at_horizon=replace(outcome.at_horizon, exposure=exposure))
        )
