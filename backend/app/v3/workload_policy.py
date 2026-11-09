"""Explicit synthetic clocks; no source period is silently converted into hours."""

from fractions import Fraction
from typing import Any, cast

from app.v3.workload_allocation import allocate_quotas
from app.v3.workload_models import BurstWindow, DemandWeight, WorkloadPolicy

POLICY_SCHEMA = "qoima.workload-policy.v3-proposal"
POLICY_VERSION = "0.1.0"


def integer(value: object, *, positive: bool = False) -> int:
    if type(value) is not int or value < (1 if positive else 0):
        raise ValueError("Clock/count requires an exact nonnegative integer")
    return value


def fields(value: object, expected: set[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != expected:
        raise ValueError("Policy object has missing or unknown fields")
    return cast(dict[str, Any], value)


def calendar_kind(value: object) -> None:
    if type(value) is not str or value not in {"normal", "burst"}:
        raise ValueError("Unknown synthetic calendar")


def validate_policy(policy: WorkloadPolicy) -> None:
    if type(policy) is not WorkloadPolicy:
        raise ValueError("Typed workload policy required")
    integer(policy.horizon_tick, positive=True)
    integer(policy.inbound_hus)
    integer(policy.outbound_hus)
    calendar_kind(policy.calendar)
    if type(policy.windows) is not tuple:
        raise ValueError("Calendar windows must be immutable")
    if (policy.calendar == "normal") != (not policy.windows):
        raise ValueError("Normal has no windows; burst requires explicit windows")
    previous_end = 0
    for window in policy.windows:
        if type(window) is not BurstWindow:
            raise ValueError("Typed burst window required")
        start, end = integer(window.start_tick), integer(window.end_tick, positive=True)
        if not previous_end <= start < end <= policy.horizon_tick:
            raise ValueError("Burst windows must be ordered, nonoverlapping and within H")
        if type(window.weight) is not Fraction or window.weight <= 0:
            raise ValueError("Burst weights require positive exact fractions")
        previous_end = end


def _window(value: object) -> BurstWindow:
    row = fields(value, {"start_tick", "end_tick", "weight"})
    weight = row["weight"]
    if type(weight) is not list or len(weight) != 2:
        raise ValueError("Burst weight requires [numerator, denominator]")
    exact = Fraction(integer(weight[0], positive=True), integer(weight[1], positive=True))
    return BurstWindow(integer(row["start_tick"]), integer(row["end_tick"]), exact)


def parse_workload_policy(value: object) -> WorkloadPolicy:
    row = fields(value, {"schema_id", "schema_version", "horizon_tick", "offered_hus", "calendar"})
    if row["schema_id"] != POLICY_SCHEMA or row["schema_version"] != POLICY_VERSION:
        raise ValueError("Unsupported workload policy version")
    offered = fields(row["offered_hus"], {"inbound", "outbound"})
    calendar = fields(row["calendar"], {"kind", "windows"})
    if type(calendar["windows"]) is not list:
        raise ValueError("Calendar windows require a JSON array")
    policy = WorkloadPolicy(
        integer(row["horizon_tick"], positive=True),
        integer(offered["inbound"]),
        integer(offered["outbound"]),
        calendar["kind"],
        tuple(_window(w) for w in calendar["windows"]),
    )
    validate_policy(policy)
    return policy


def arrival_ticks(policy: WorkloadPolicy, count: int) -> tuple[int, ...]:
    validate_policy(policy)
    integer(count)
    if not count:
        return ()
    if policy.calendar == "normal":
        return tuple(index * policy.horizon_tick // count for index in range(count))
    width = len(str(len(policy.windows)))
    weights = tuple(
        DemandWeight("window", str(i).zfill(width), window.weight)
        for i, window in enumerate(policy.windows)
    )
    quotas = allocate_quotas(weights, count)
    return tuple(
        window.start_tick + index * (window.end_tick - window.start_tick) // quota.count
        for window, quota in zip(policy.windows, quotas, strict=True)
        for index in range(quota.count)
    )
