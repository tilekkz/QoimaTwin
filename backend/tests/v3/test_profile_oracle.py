"""Independent geometry and clock oracles written before the compiler."""

from fractions import Fraction

import pytest

from app.v3.materialize import calendar_tick
from app.v3.profile_geometry import overlaps, segment_bounds


def test_hand_connector_envelope() -> None:
    # 8m horizontal leg, 0.4m radius -> [129.6,62.6,138.4,63.4].
    assert segment_bounds(
        (Fraction(130), Fraction(63)), (Fraction(138), Fraction(63)), Fraction("0.4")
    ) == (Fraction("129.6"), Fraction("62.6"), Fraction("138.4"), Fraction("63.4"))
    unit = (Fraction(0), Fraction(0), Fraction(1), Fraction(1))
    assert not overlaps(unit, (Fraction(1), Fraction(0), Fraction(2), Fraction(1)))
    assert overlaps(unit, (Fraction("0.99"), Fraction(0), Fraction(2), Fraction(1)))


def test_hand_fixed_calendar() -> None:
    assert calendar_tick("0") == 0
    assert calendar_tick("1.0000001") == 1_000_001
    for value in ("-1", "nan", "inf"):
        with pytest.raises(ValueError):
            calendar_tick(value)
