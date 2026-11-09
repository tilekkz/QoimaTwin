"""Storage fullness denominators and reservations from independent hand arithmetic."""

from dataclasses import replace
from fractions import Fraction as F
from typing import cast

import pytest

from app.v3.storage_fullness_models import ModuleCapacity, SlotCapacity, SlotLoad
from app.v3.storage_fullness_projection import project_storage


def capacities() -> tuple[SlotCapacity, ...]:
    return (
        SlotCapacity("a", "m", "z", True, False, False, 1, F(10), F(2)),
        SlotCapacity("b", "m", "z", True, False, False, 1, F(10), F(2)),
        SlotCapacity("c", "m", "z", False, True, True, 1, F(10), F(2)),
    )


def modules() -> tuple[ModuleCapacity, ...]:
    return (ModuleCapacity("m", 3, F(25)),)


def test_physical_empty_active_empty_and_reserved_are_distinct() -> None:
    report = project_storage(capacities(), modules(), (SlotLoad("a", 1, 2, F(4), F(1)),), ("b",))
    total = report["total"]
    assert (total["physical_slots"], total["occupied_slots"], total["empty_slots"]) == (3, 1, 2)
    assert (total["active_slots"], total["active_empty_slots"]) == (2, 1)
    assert total["unreserved_active_empty_slots"] == 0
    assert (total["reserved_slots"], total["blocked_slots"], total["reserve_only_slots"]) == (
        1,
        1,
        1,
    )
    assert total["occupied_fraction"] == {"numerator": 1, "denominator": 3}
    assert total["active_occupied_fraction"] == {"numerator": 1, "denominator": 2}
    assert total["volume_fraction"] == {"numerator": 1, "denominator": 6}
    assert total["slot_payload_fraction"] == {"numerator": 2, "denominator": 15}
    assert report["modules"][0]["module_payload_fraction"] == {"numerator": 4, "denominator": 25}
    assert report["operational_admission"] is False


def test_empty_wrapper_still_occupies_a_slot_and_its_outer_volume() -> None:
    report = project_storage(capacities(), modules(), (SlotLoad("a", 1, 0, F(".1"), F(1)),), ("a",))
    assert report["total"]["occupied_slots"] == 1
    assert report["total"]["units"] == 0
    assert report["total"]["reserved_slots"] == 1
    assert report["total"]["unreserved_active_empty_slots"] == 1


def test_handoff_observation_frees_source_only_after_container_leaves() -> None:
    before = project_storage(capacities(), modules(), (SlotLoad("a", 1, 2, F(4), F(1)),), ())
    after = project_storage(capacities(), modules(), (), ("b",))
    assert before["total"]["occupied_slots"] == 1
    assert after["total"]["occupied_slots"] == 0
    assert after["total"]["unreserved_active_empty_slots"] == 1


def test_no_active_capacity_is_unavailable_instead_of_zero_percent() -> None:
    report = project_storage((capacities()[2],), modules(), (), ())
    assert report["total"]["active_occupied_fraction"] is None
    assert report["total"]["occupied_fraction"] == {"numerator": 0, "denominator": 1}


@pytest.mark.parametrize(
    "loads,reserved",
    [
        ((SlotLoad("unknown", 1, 1, F(1), F(1)),), ()),
        ((SlotLoad("a", 2, 1, F(1), F(1)),), ()),
        ((SlotLoad("a", 1, 1, F(11), F(1)),), ()),
        ((SlotLoad("a", 1, 1, F(1), F(3)),), ()),
        ((SlotLoad("a", 0, 1, F(1), F(1)),), ()),
        ((SlotLoad("a", 1, -1, F(1), F(1)),), ()),
        ((SlotLoad("a", cast(int, True), 1, F(1), F(1)),), ()),
        ((SlotLoad("a", 1, 1, cast(F, 1), F(1)),), ()),
        ((), ("unknown",)),
        ((), ("a", "a")),
    ],
)
def test_invalid_observed_projection_is_rejected(
    loads: tuple[SlotLoad, ...], reserved: tuple[str, ...]
) -> None:
    with pytest.raises(ValueError):
        project_storage(capacities(), modules(), loads, reserved)


def test_module_limit_is_not_replaced_by_sum_of_slot_limits() -> None:
    loads = tuple(SlotLoad(key, 1, 1, F(9), F(1)) for key in ("a", "b", "c"))
    with pytest.raises(ValueError, match="module"):
        project_storage(capacities(), modules(), loads, ())


def test_duplicate_capacity_and_numeric_boolean_alias_are_rejected() -> None:
    with pytest.raises(ValueError):
        project_storage((*capacities(), capacities()[0]), modules(), (), ())
    with pytest.raises(ValueError):
        project_storage((replace(capacities()[0], active=cast(bool, 1)),), modules(), (), ())
