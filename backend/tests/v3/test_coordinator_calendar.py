"""Hand clocks for explicit existing jobs; no expected value comes from a DES run."""

from copy import deepcopy
from dataclasses import replace
from typing import Any

import pytest

from app.storage.canonical_json import parse_json
from app.v3.coordinator_calendar import materialize_calendar
from app.v3.coordinator_calendar_models import CalendarLane, CoordinatorCalendar
from tests.v3.test_coordinator_profile_fixtures import coordinator_document


def calendar() -> CoordinatorCalendar:
    return CoordinatorCalendar(
        10,
        20,
        "Hand example: two arrivals in [2,10), not a source rate",
        (CalendarLane("picks", "unit_order", ("O1", "O2"), 2, 10),),
    )


def test_two_jobs_have_exact_half_open_hand_arrivals_without_input_mutation() -> None:
    value = coordinator_document()
    before = deepcopy(value)
    result = materialize_calendar(value, calendar())
    changed = parse_json(result.choices_bytes)
    assert value == before
    assert [row["arrival_tick"] for row in changed["orders"]] == [2, 6]
    assert (changed["horizon_tick"], changed["end_tick"]) == (10, 20)
    expected = deepcopy(value)
    expected["horizon_tick"], expected["end_tick"] = 10, 20
    expected["orders"][0]["arrival_tick"] = 2
    expected["orders"][1]["arrival_tick"] = 6
    assert changed == expected
    assert result.counts == (("unit_order", 2), ("receipt", 0), ("whole_order", 0))
    assert result.operational_admission is False


def test_uniform_rounding_preserves_declared_job_order_and_same_tick_arrivals() -> None:
    value = coordinator_document()
    value["orders"].append({**deepcopy(value["orders"][0]), "order_id": "O3"})
    choices = CoordinatorCalendar(
        10,
        20,
        "Integer hand arithmetic",
        (CalendarLane("picks", "unit_order", ("O3", "O1", "O2"), 0, 10),),
    )
    result = parse_json(materialize_calendar(value, choices).choices_bytes)
    assert {row["order_id"]: row["arrival_tick"] for row in result["orders"]} == {
        "O1": 3,
        "O2": 6,
        "O3": 0,
    }
    lane = replace(choices.lanes[0], end_tick=1)
    dense = parse_json(materialize_calendar(value, replace(choices, lanes=(lane,))).choices_bytes)
    assert [row["arrival_tick"] for row in dense["orders"]] == [0, 0, 0]


def test_lane_table_permutation_is_canonical_but_job_order_is_meaningful() -> None:
    left = CalendarLane("late", "unit_order", ("O1",), 5, 10)
    right = CalendarLane("early", "unit_order", ("O2",), 0, 5)
    value = coordinator_document()
    a = materialize_calendar(value, replace(calendar(), lanes=(left, right)))
    b = materialize_calendar(value, replace(calendar(), lanes=(right, left)))
    assert (a.choices_bytes, a.calendar_bytes, a.offered_workload_hash) == (
        b.choices_bytes,
        b.calendar_bytes,
        b.offered_workload_hash,
    )
    reversed_jobs = replace(calendar().lanes[0], job_ids=("O2", "O1"))
    c = materialize_calendar(value, replace(calendar(), lanes=(reversed_jobs,)))
    assert c.offered_workload_hash != materialize_calendar(value, calendar()).offered_workload_hash


@pytest.mark.parametrize("job_ids", [("O1",), ("O1", "O1"), ("O1", "missing")])
def test_every_job_is_covered_exactly_once(job_ids: tuple[str, ...]) -> None:
    lane = replace(calendar().lanes[0], job_ids=job_ids)
    with pytest.raises(ValueError, match="CALENDAR_"):
        materialize_calendar(coordinator_document(), replace(calendar(), lanes=(lane,)))


def test_a_job_cannot_appear_in_two_lanes_or_the_wrong_stream() -> None:
    first = calendar().lanes[0]
    for second in (replace(first, lane_id="duplicate"), replace(first, kind="receipt")):
        with pytest.raises(ValueError, match="CALENDAR_"):
            materialize_calendar(coordinator_document(), replace(calendar(), lanes=(first, second)))


@pytest.mark.parametrize("start,end", [(0, 11), (10, 10), (5, 4), (-1, 5)])
def test_windows_must_be_positive_half_open_subsets_of_horizon(start: int, end: int) -> None:
    lane = replace(calendar().lanes[0], start_tick=start, end_tick=end)
    with pytest.raises(ValueError, match="CALENDAR_"):
        materialize_calendar(coordinator_document(), replace(calendar(), lanes=(lane,)))


@pytest.mark.parametrize("invalid", [True, 10.0, "10"])
def test_clock_types_are_exact_even_when_values_compare_equal(invalid: Any) -> None:
    with pytest.raises(ValueError, match="CALENDAR_"):
        materialize_calendar(coordinator_document(), replace(calendar(), horizon_tick=invalid))


def test_offer_hash_is_bounded_and_cannot_be_used_as_a_physical_common_hash() -> None:
    value = coordinator_document()
    first = materialize_calendar(value, calendar())
    value["role_intents"] = []
    value["carts"][0]["max_gross_kg"]["numerator"] += 1
    second = materialize_calendar(value, calendar())
    assert first.offered_workload_hash == second.offered_workload_hash
    assert first.choices_bytes != second.choices_bytes


def test_empty_population_requires_an_explicit_empty_calendar() -> None:
    value = coordinator_document()
    value["orders"], value["unit_assignments"] = [], []
    result = materialize_calendar(value, replace(calendar(), lanes=()))
    assert result.counts == (("unit_order", 0), ("receipt", 0), ("whole_order", 0))
    with pytest.raises(ValueError, match="CALENDAR_"):
        materialize_calendar(value, calendar())
