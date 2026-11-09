"""V3 duration expectations are hand arithmetic, not simulation output."""

from decimal import Decimal
from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.v3.runtime_time import TICKS_PER_SECOND, operation_ticks, travel_ticks


@pytest.mark.parametrize(
    "seconds,ticks",
    [
        (0, 0),
        (1, 1_000_000),
        ("0.8", 800_000),
        (0.1, 100_000),
        (Fraction(1, 3), 333_334),
        (Decimal("0.0000001"), 1),
        (Decimal("1.00000000001"), 1_000_001),
    ],
)
def test_each_duration_rounds_up_to_microseconds(seconds: object, ticks: int) -> None:
    assert TICKS_PER_SECOND == 1_000_000
    assert operation_ticks(seconds) == ticks


@pytest.mark.parametrize(
    "seconds", [True, False, -1, "-0.001", float("nan"), float("inf"), Decimal("NaN"), "bad", None]
)
def test_invalid_duration_is_rejected(seconds: object) -> None:
    with pytest.raises(ValueError):
        operation_ticks(seconds)


def test_travel_uses_exact_decimal_ratio_then_one_ceiling() -> None:
    assert travel_ticks("0.5", "0.55") == 909_091  # (10/11)s rounded up once.
    assert travel_ticks("1.9634954084936207", "0.55") == 3_569_992
    assert travel_ticks(0, "1.3") == 0
    assert operation_ticks(Fraction(1, 3)) * 3 == 1_000_002


@pytest.mark.parametrize(
    "length,speed", [(-1, 1), (1, 0), (1, -1), (1, True), (1, float("inf")), (float("nan"), 1)]
)
def test_travel_rejects_invalid_distance_or_speed(length: object, speed: object) -> None:
    with pytest.raises(ValueError):
        travel_ticks(length, speed)


@given(st.integers(min_value=0, max_value=10**12), st.integers(min_value=1, max_value=10**9))
def test_quantized_duration_is_never_early_and_adds_less_than_one_tick(
    numerator: int, denominator: int
) -> None:
    duration = Fraction(numerator, denominator)
    quantized = Fraction(operation_ticks(duration), TICKS_PER_SECOND)
    assert duration <= quantized < duration + Fraction(1, TICKS_PER_SECOND)
