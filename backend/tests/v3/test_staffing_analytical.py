"""Literal N4 availability arithmetic, recorded before implementation; no DES oracle."""

from dataclasses import replace

import pytest

from app.v3.staff_registry import compile_staff_registry
from app.v3.staffing_analytical import analyze_staffing, schedule_eligible_actor_ids
from app.v3.staffing_models import AnalyticalCover
from tests.v3.test_staff_registry_fixtures import SECOND, registry_document


def covers() -> tuple[AnalyticalCover, ...]:
    return (
        AnalyticalCover(
            "cover11", "P11", "PK05", 100 * SECOND, 160 * SECOND, 4 * SECOND, 4 * SECOND
        ),
        AnalyticalCover(
            "cover12", "P12", "PK06", 100 * SECOND, 160 * SECOND, 6 * SECOND, 6 * SECOND
        ),
    )


def test_paid_transitions_consume_twenty_seconds_and_add_only_one_hundred() -> None:
    registry = compile_staff_registry(registry_document())
    baseline = analyze_staffing(registry, (), 100 * SECOND, 160 * SECOND)
    candidate = analyze_staffing(registry, covers(), 100 * SECOND, 160 * SECOND)
    assert baseline.role_person_ticks("pack") == 240 * SECOND
    assert candidate.role_person_ticks("pack") == 340 * SECOND
    assert candidate.transition_person_ticks == 20 * SECOND
    assert candidate.role_person_ticks("pick") == baseline.role_person_ticks("pick") - 120 * SECOND
    assert candidate.unavailable_person_ticks == 120 * SECOND
    assert candidate.roster_person_ticks == 1440 * SECOND
    assert sum(value for _, value in candidate.role_ticks) == 1300 * SECOND
    assert not candidate.operational_admission
    assert not candidate.full_n4_pass


@pytest.mark.parametrize(
    "second,count", [(100, 4), (104, 5), (106, 6), (154, 5), (156, 4), (160, 6)]
)
def test_half_open_schedule_pool_boundaries(second: int, count: int) -> None:
    registry = compile_staff_registry(registry_document())
    assert len(schedule_eligible_actor_ids(registry, covers(), "pack", second * SECOND)) == count


def test_clipping_at_105_has_no_future_arrival_and_zero_window_is_zero() -> None:
    registry = compile_staff_registry(registry_document())
    clipped = analyze_staffing(registry, covers(), 100 * SECOND, 105 * SECOND)
    assert clipped.role_person_ticks("pack") == 21 * SECOND  # four primaries*5 + P11*1
    assert clipped.transition_person_ticks == 9 * SECOND  # P11*4 + P12*5
    empty = analyze_staffing(registry, covers(), 105 * SECOND, 105 * SECOND)
    assert empty.roster_person_ticks == empty.transition_person_ticks == 0


def test_explicit_deferred_clean_start_reduces_p11_window_to_42_seconds() -> None:
    registry = compile_staff_registry(registry_document())
    delayed = (replace(covers()[0], start_tick=110 * SECOND), covers()[1])
    result = analyze_staffing(registry, delayed, 100 * SECOND, 160 * SECOND)
    assert result.role_person_ticks("pack") == 330 * SECOND  # 240+42+48
    assert result.transition_person_ticks == 20 * SECOND


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_skill",
        "unavailable_helper",
        "primary_not_on_break",
        "overlapping_actor",
        "overlapping_station",
        "unknown_actor",
        "unknown_station",
    ],
)
def test_invalid_analytical_covers_are_rejected(mutation: str) -> None:
    document = registry_document()
    choices = covers()
    if mutation == "missing_skill":
        document["workers"][10]["eligible_roles"] = ["pick"]
    elif mutation == "unavailable_helper":
        document["unavailability"].append(dict(document["unavailability"][0], actor_id="P11"))
    elif mutation == "primary_not_on_break":
        document["unavailability"].pop(0)
    elif mutation == "overlapping_actor":
        choices = (*choices, replace(choices[0], cover_id="extra", station_id="PK06"))
    elif mutation == "overlapping_station":
        choices = (choices[0], replace(choices[1], station_id="PK05"))
    elif mutation == "unknown_actor":
        choices = (replace(choices[0], actor_id="ghost"),)
    else:
        choices = (replace(choices[0], station_id="PK07"),)
    with pytest.raises(ValueError):
        analyze_staffing(compile_staff_registry(document), choices, 0, 200 * SECOND)
