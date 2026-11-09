"""Necessary straight-gate arithmetic is never a swept-path certificate."""

from fractions import Fraction as F
from typing import Any

import pytest

from app.v3.long_freight_checks import straight_gate_fits


def test_exact_gate_boundary_and_both_clearance_sides() -> None:
    assert not straight_gate_fits((F("4.2"), F("1.32")), (F("4.19"), F(3)), F(0))
    assert straight_gate_fits((F("4.2"), F("1.32")), (F("4.2"), F(3)), F(0))
    assert not straight_gate_fits((F("4.2"), F("1.32")), (F("4.29"), F(3)), F(".05"))
    assert straight_gate_fits((F("4.2"), F("1.32")), (F("4.3"), F(3)), F(".05"))
    assert not straight_gate_fits((F("4.2"), F("1.32")), (F(6), F("1.31")), F(0))


@pytest.mark.parametrize("bad", [True, 0, 0.0, F(-1)])
def test_gate_scalar_aliases_and_negative_clearance_reject(bad: Any) -> None:
    with pytest.raises(ValueError):
        straight_gate_fits((F("4.2"), F("1.32")), (F(6), F(3)), bad)
