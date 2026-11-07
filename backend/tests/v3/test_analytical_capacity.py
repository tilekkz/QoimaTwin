"""F2 hypothetical geometry/mass oracle, not production admission or arbitrary bin packing."""

from fractions import Fraction as F

import pytest

from app.v3.analytical_capacity import BoxFixture, SlotFixture, evaluate_fixture_fit


def box() -> BoxFixture:
    return BoxFixture((F("0.60"), F("0.40"), F("0.30")), F(8))


def test_f2_geometry_and_mass_are_independent_limits() -> None:
    slot_a = SlotFixture((F("0.55"), F("0.45"), F("0.35")), F(15))
    slot_b = SlotFixture((F("0.65"), F("0.45"), F("0.35")), F(7))
    slot_c = SlotFixture((F("1.25"), F("0.45"), F("0.35")), F(15))
    assert evaluate_fixture_fit(box(), slot_a).reason == "DIMENSION_MISMATCH"
    assert evaluate_fixture_fit(box(), slot_b).reason == "OVERWEIGHT"
    single = evaluate_fixture_fit(box(), slot_c)
    assert single.accepted and single.reason == "DESIGN_COMPATIBLE"
    double = evaluate_fixture_fit(box(), slot_c, quantity=2)
    assert double.geometric_capacity == 2
    assert double.gross_mass_kg == 16
    assert not double.accepted and double.reason == "OVERWEIGHT"
    assert double.source_kind == "analytical_fixture"


def test_f2_orientation_permission_precedes_geometric_convenience() -> None:
    tall = SlotFixture((F("0.30"), F("0.60"), F("0.40")), F(8))
    assert evaluate_fixture_fit(box(), tall, orientations=((0, 1, 2),)).reason == (
        "DIMENSION_MISMATCH"
    )
    allowed = evaluate_fixture_fit(box(), tall, orientations=((2, 0, 1),))
    assert allowed.accepted and allowed.orientation == (2, 0, 1)
    assert evaluate_fixture_fit(box(), tall, orientations=()).reason == "ORIENTATION_FORBIDDEN"


def test_f2_exact_boundary_and_tiny_excess_are_not_rounded_into_fit() -> None:
    exact = SlotFixture(box().dimensions_m, F(8))
    assert evaluate_fixture_fit(box(), exact).accepted
    excess = BoxFixture((F("0.6000000001"), F("0.40"), F("0.30")), F(8))
    assert evaluate_fixture_fit(excess, exact).reason == "DIMENSION_MISMATCH"
    assert evaluate_fixture_fit(box(), exact, quantity=2).reason == "SLOT_CAPACITY"


@pytest.mark.parametrize("quantity", [0, -1, True])
def test_f2_rejects_nonpositive_or_boolean_counts(quantity: int) -> None:
    with pytest.raises(ValueError):
        evaluate_fixture_fit(box(), SlotFixture(box().dimensions_m, F(8)), quantity)


def test_f2_rejects_invalid_axis_permutation() -> None:
    with pytest.raises(ValueError):
        evaluate_fixture_fit(
            box(), SlotFixture(box().dimensions_m, F(8)), orientations=((0, 0, 2),)
        )


def test_f2_rejects_invalid_physical_input() -> None:
    with pytest.raises(ValueError):
        BoxFixture((F(0), F(1), F(1)), F(1))
    with pytest.raises(ValueError):
        SlotFixture((F(1), F(1), F(1)), F(-1))
