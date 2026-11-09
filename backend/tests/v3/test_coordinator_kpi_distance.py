"""Ten metres in five seconds, plus four metres in two; no engine-derived oracle."""

from dataclasses import replace

import pytest

from app.v3.coordinator_metrics_distance import distances
from app.v3.coordinator_models import RoleView
from tests.v3.test_coordinator_kpi_fixtures import S, move, outcome, point, profile


@pytest.mark.parametrize(("seconds", "numerator"), [(2, 0), (4, 4), (7, 10), (8, 12), (9, 14)])
def test_distance_clips_open_operations_and_exact_boundaries(seconds: int, numerator: int) -> None:
    value = profile()
    snapshot = point(value, seconds * S)
    events = (move(0, 2 * S, 7 * S, 10), move(1, 7 * S, 9 * S, 4))
    result = distances(value, outcome(snapshot, events), snapshot)
    actor = next(row for row in result["actors"] if row["actor_id"] == "P01")
    assert actor["paid_distance_m"] == {"numerator": numerator, "denominator": 1}
    assert len(result["actors"]) == 24


def test_duplicate_or_overlapping_actor_operation_is_not_double_counted() -> None:
    value = profile()
    snapshot = point(value, 8 * S)
    first = move(0, 2 * S, 7 * S, 10)
    for events in ((first, replace(first, seq=1)), (first, move(1, 6 * S, 8 * S, 4))):
        with pytest.raises(ValueError, match="overlap"):
            distances(value, outcome(snapshot, events), snapshot)


def test_service_without_route_does_not_create_travel() -> None:
    value = profile()
    snapshot = point(value, 10 * S)
    event = move(0, 2 * S, 7 * S, 10)
    assert event.operation is not None
    event = replace(event, operation=replace(event.operation, kind="pick", route=None))
    result = distances(value, outcome(snapshot, (event,)), snapshot)
    assert result["total_paid_distance_m"] == {"numerator": 0, "denominator": 1}


def test_distance_records_existing_picker_in_actual_helper_and_transition_roles() -> None:
    value = profile()
    role = RoleView("I11", "P11", "PK05", "returning", 2 * S, 7 * S, 9 * S, None, None)
    snapshot = replace(point(value, 11 * S), roles=(role,))
    events = (
        move(0, 2 * S, 7 * S, 10, actor="P11"),
        move(1, 7 * S, 9 * S, 4, actor="P11"),
        move(2, 9 * S, 12 * S, 6, actor="P11"),
    )
    result = distances(value, outcome(snapshot, events), snapshot)
    assert result["by_effective_role_m"] == {
        "transition": {"numerator": 14, "denominator": 1},
        "pack": {"numerator": 4, "denominator": 1},
    }
    actor = next(row for row in result["actors"] if row["actor_id"] == "P11")
    assert actor["primary_role"] == "pick"
