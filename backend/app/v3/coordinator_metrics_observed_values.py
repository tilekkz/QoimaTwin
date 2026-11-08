"""Exact half-open arithmetic for observed KPI reducers, not an admission policy."""

from fractions import Fraction

from app.v3.coordinator_metrics_values import integer
from app.v3.interface import Json


def elapsed(start: int, end: int | None, cutoff: int) -> int:
    start, cutoff = integer(start), integer(cutoff)
    if end is not None and integer(end) < start:
        raise ValueError("KPI interval ends before it starts")
    return max(0, min(cutoff, cutoff if end is None else end) - start)


def rational(value: Fraction) -> Json:
    if type(value) is not Fraction:
        raise ValueError("KPI rational quantity requires an exact Fraction")
    return {"numerator": value.numerator, "denominator": value.denominator}


def no_overlap(intervals: list[tuple[int, int]]) -> None:
    until = 0
    for start, end in sorted(intervals):
        if start < until:
            raise ValueError("KPI exclusive resource intervals overlap")
        until = end


def unavailable(reason: str) -> Json:
    return {"available": False, "value": None, "reason": reason}
