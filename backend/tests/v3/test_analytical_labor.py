"""F3 literal detour and two-person arithmetic; no scheduling or production-rate oracle."""

from fractions import Fraction as F

import pytest

from app.v3.analytical_labor import CrewFixture, TravelFixture, compare_crews, cycle_cost


def test_f3_detour_elapsed_time_and_person_labor_are_separate() -> None:
    travel = TravelFixture((F(4), F(6), F(4)), F("1.4"))
    light = CrewFixture(people=1, take_s=F(6), place_s=F(6))
    heavy = CrewFixture(people=2, take_s=F(20), place_s=F(20))
    result = compare_crews(travel, light, heavy)
    assert result.baseline.round_trip_m == result.candidate.round_trip_m == 28
    assert result.baseline.travel_s == result.candidate.travel_s == 20
    assert (result.baseline.elapsed_s, result.baseline.labor_person_s) == (F(32), F(32))
    assert (result.candidate.elapsed_s, result.candidate.labor_person_s) == (F(60), F(120))
    assert result.elapsed_difference_s == 28
    assert result.labor_difference_person_s == 88
    assert result.source_kind == "analytical_fixture"


def test_f3_noop_keeps_both_differences_zero() -> None:
    travel = TravelFixture((F(4), F(6), F(4)), F("1.4"))
    crew = CrewFixture(people=1, take_s=F(6), place_s=F(6))
    result = compare_crews(travel, crew, crew)
    assert (result.elapsed_difference_s, result.labor_difference_person_s) == (F(0), F(0))


def test_f3_exact_rational_time_preserved() -> None:
    result = cycle_cost(TravelFixture((F(1),), F(3)), CrewFixture(1, F(0), F(0)))
    assert result.travel_s == result.elapsed_s == result.labor_person_s == F(2, 3)


@pytest.mark.parametrize("people", [0, -1, True])
def test_f3_rejects_invalid_crew_size(people: int) -> None:
    with pytest.raises(ValueError):
        CrewFixture(people, F(6), F(6))


def test_f3_rejects_impossible_route_or_service() -> None:
    with pytest.raises(ValueError):
        TravelFixture((F(1),), F(0))
    with pytest.raises(ValueError):
        TravelFixture((F(-1),), F(1))
    with pytest.raises(ValueError):
        CrewFixture(1, F(-1), F(0))
