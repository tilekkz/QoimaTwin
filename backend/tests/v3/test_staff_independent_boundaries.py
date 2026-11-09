"""Adjacent half-open periods and separate common/allocation identity hand controls."""

from typing import Any

import pytest

from app.v3.staff_registry import compile_staff_registry, require_same_registry
from app.v3.staffing_analytical import analyze_staffing, schedule_eligible_actor_ids
from app.v3.staffing_identity import analytical_allocation_hash
from app.v3.staffing_models import AnalyticalCover
from tests.v3.test_staff_registry_fixtures import registry_document


def _document(gap: int = 0) -> dict[str, Any]:
    document = registry_document()
    document["unavailability"] = [
        {"actor_id": actor, "start_tick": start, "end_tick": end, "reason": reason}
        for actor, start, end, reason in (
            ("K05", 10, 15, "first"),
            ("K05", 15 + gap, 20, "second"),
            ("P11", 0, 10, "before"),
            ("P11", 20, 21, "after"),
        )
    ]
    return document


def test_contiguous_primary_breaks_and_touching_helper_periods_are_half_open() -> None:
    registry = compile_staff_registry(_document())
    covers = (AnalyticalCover("C", "P11", "PK05", 10, 20, 2, 3),)
    result = analyze_staffing(registry, covers, 10, 20)
    assert result.role_person_ticks("pack") == 55  # five*10 + helper[12,17)
    assert result.role_person_ticks("pick") == 110
    assert result.transition_person_ticks == 5
    assert result.unavailable_person_ticks == 10
    assert result.roster_person_ticks == 240
    assert sum(n for _, n in result.role_ticks) == 225
    assert "P11" not in schedule_eligible_actor_ids(registry, covers, "pack", 11)
    assert "P11" in schedule_eligible_actor_ids(registry, covers, "pack", 12)
    assert "P11" not in schedule_eligible_actor_ids(registry, covers, "pack", 17)
    assert "P11" not in schedule_eligible_actor_ids(registry, covers, "pick", 20)
    assert "P11" in schedule_eligible_actor_ids(registry, covers, "pick", 21)
    assert not result.operational_admission and not result.full_n4_pass


def test_one_tick_gap_cannot_be_filled_by_union_of_primary_breaks() -> None:
    registry = compile_staff_registry(_document(gap=1))
    covers = (AnalyticalCover("C", "P11", "PK05", 10, 20, 2, 3),)
    with pytest.raises(ValueError, match="ANALYTICAL_PRIMARY_BREAK_REQUIRED"):
        analyze_staffing(registry, covers, 10, 20)


def test_equal_allocation_and_exposure_do_not_prove_common_registry_equality() -> None:
    document = _document()
    original = compile_staff_registry(document)
    document["unavailability"][0]["reason"] = "different_explicit_assumption"
    changed = compile_staff_registry(document)
    covers = (AnalyticalCover("C", "P11", "PK05", 10, 20, 2, 3),)
    allocation = analytical_allocation_hash(original, covers)
    assert allocation == analytical_allocation_hash(changed, covers)
    assert analyze_staffing(original, covers, 10, 20) == analyze_staffing(changed, covers, 10, 20)
    assert original.registry_common_hash != changed.registry_common_hash
    with pytest.raises(ValueError, match="REGISTRY_COMMON_INPUT_DRIFT"):
        require_same_registry(original, changed)
