"""Explicit synthetic clocks; C10 does not provide an hourly arrival rate."""

from dataclasses import replace
from fractions import Fraction as F
from typing import cast

import pytest

from app.v3.workload_models import BurstWindow, WorkloadPolicy
from app.v3.workload_policy import arrival_ticks, parse_workload_policy
from tests.v3.test_workload_fixtures import policy_document


def test_normal_calendar_exact_half_open_ticks_and_zero_one_limits() -> None:
    policy = parse_workload_policy(policy_document())
    assert arrival_ticks(policy, 4) == (0, 2, 5, 7)
    assert arrival_ticks(policy, 1) == (0,)
    assert arrival_ticks(policy, 0) == ()
    assert arrival_ticks(replace(policy, horizon_tick=1), 4) == (0, 0, 0, 0)


def test_explicit_burst_weights_allocate_whole_counts_then_fill_each_window() -> None:
    policy = WorkloadPolicy(10, 4, 4, "burst", (BurstWindow(2, 4, F(1)), BurstWindow(7, 8, F(1))))
    assert arrival_ticks(policy, 4) == (2, 3, 7, 7)
    assert arrival_ticks(policy, 1) == (2,)  # equal remainders tie by earlier window


@pytest.mark.parametrize(
    "case", ["extra", "schema", "boolean", "negative", "float", "normal_windows"]
)
def test_policy_json_rejects_unknown_or_malformed_fields(case: str) -> None:
    value = policy_document()
    if case == "extra":
        value["engine_seed"] = 1
    elif case == "schema":
        value["schema_version"] = "source-hourly"
    elif case == "boolean":
        value["horizon_tick"] = True
    elif case == "negative":
        value["offered_hus"] = {"inbound": -1, "outbound": 0}
    elif case == "float":
        value["offered_hus"] = {"inbound": 1.0, "outbound": 0}
    else:
        value["calendar"] = {
            "kind": "normal",
            "windows": [{"start_tick": 0, "end_tick": 1, "weight": [1, 1]}],
        }
    with pytest.raises(ValueError):
        parse_workload_policy(value)


@pytest.mark.parametrize(
    "windows",
    [
        (),
        (BurstWindow(0, 11, F(1)),),
        (BurstWindow(1, 1, F(1)),),
        (BurstWindow(0, 6, F(1)), BurstWindow(5, 8, F(1))),
        (BurstWindow(0, 1, F(0)),),
    ],
)
def test_direct_burst_policy_rejects_invalid_windows(windows: tuple[BurstWindow, ...]) -> None:
    with pytest.raises(ValueError):
        arrival_ticks(WorkloadPolicy(10, 1, 1, "burst", windows), 1)


@pytest.mark.parametrize("invalid", [True, float("nan"), float("inf"), -1])
def test_direct_clock_rejects_non_integer_or_invalid_horizon(invalid: object) -> None:
    with pytest.raises(ValueError):
        arrival_ticks(WorkloadPolicy(cast(int, invalid), 0, 0, "normal"), 0)
