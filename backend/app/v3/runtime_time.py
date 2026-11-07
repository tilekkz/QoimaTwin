"""V3 operation durations use an explicit ceiling to microseconds (ADR 0026)."""

from decimal import Decimal
from fractions import Fraction

TICKS_PER_SECOND = 1_000_000
DURATION_ROUNDING = "ceil_each_positive_operation"


def nonnegative_fraction(value: object) -> Fraction:
    """Interpret decimal inputs exactly; never accept bool, nonfinite or negative values."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal, Fraction)):
        raise ValueError("a finite nonnegative number is required")
    try:
        number = value if isinstance(value, Fraction) else Fraction(str(value))
    except (ValueError, ZeroDivisionError, OverflowError):
        raise ValueError("a finite nonnegative number is required") from None
    if number < 0:
        raise ValueError("a finite nonnegative number is required")
    return number


def operation_ticks(seconds: object) -> int:
    """Ceil one complete operation; zero denotes explicitly instantaneous work.

    This is not an arrival/window policy. Materialized timestamps need a separate
    declared representation rule; calling this function must not invent arrivals.
    """
    scaled = nonnegative_fraction(seconds) * TICKS_PER_SECOND
    return -(-scaled.numerator // scaled.denominator)


def travel_ticks(length_m: object, speed_m_s: object) -> int:
    """Compute length/speed exactly, then round once at the operation boundary."""
    length, speed = nonnegative_fraction(length_m), nonnegative_fraction(speed_m_s)
    if speed == 0:
        raise ValueError("travel speed must be positive")
    return operation_ticks(length / speed)
