"""Exact role endpoints are counts at T and exposure on the half-open prefix."""

from dataclasses import replace

from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.staff_registry import compile_staff_registry
from tests.v3.test_coordinator_fixtures import staffing_profile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor
from tests.v3.test_staff_registry_fixtures import registry_document


def test_arrival_exactly_at_horizon_has_no_invented_positive_role_exposure() -> None:
    result = CoordinatorEngine(staffing_profile(), receipt_conveyor()).run(
        106 * SECOND, 106 * SECOND
    )
    state = result.at_horizon
    assert state == result.at_end and result.status == "partial"
    roles = {row.actor_id: row for row in state.roles}
    assert roles["P11"].activated_tick == 104 * SECOND
    assert roles["P12"].activated_tick == 106 * SECOND
    assert all(row.status == "active" and row.restored_tick is None for row in roles.values())
    assert dict(state.exposure.role_ticks)["pack"] == 626 * SECOND
    assert dict(state.exposure.role_ticks)["pick"] == 1260 * SECOND
    assert state.exposure.transition_ticks == 10 * SECOND
    assert state.exposure.unavailable_ticks == 12 * SECOND
    assert (
        sum(value for _, value in state.exposure.role_ticks)
        + state.exposure.transition_ticks
        + state.exposure.unavailable_ticks
        == 2544 * SECOND
    )
    assert result.business_complete_tick == 0 and result.resource_drained_tick is None
    assert result.observation_end_tick == 106 * SECOND
    assert state.stock == result.checkpoints[0].stock
    assert not any(event.kind == "role_restored" for event in result.events)


def test_paid_restoration_settles_before_helpers_own_break_at_the_same_tick() -> None:
    profile = staffing_profile()
    document = registry_document()
    document["unavailability"].extend(
        {
            "actor_id": actor,
            "start_tick": 160 * SECOND,
            "end_tick": 170 * SECOND,
            "reason": "helper_break_after_actual_restoration",
        }
        for actor in ("P11", "P12")
    )
    profile = replace(profile, registry=compile_staff_registry(document))
    result = CoordinatorEngine(profile, receipt_conveyor()).run(160 * SECOND, 160 * SECOND)
    assert result.status == "complete" and result.staffing_status == "valid"
    assert not result.constraint_violations and not result.at_end.leases
    assert all(row.restored_tick == 160 * SECOND for row in result.at_end.roles)
    actors = {row.actor_id: row for row in result.at_end.actor_roles}
    assert not actors["P11"].available and not actors["P12"].available
    assert actors["K05"].available and actors["K06"].available
    assert result.at_end.exposure.unavailable_ticks == 120 * SECOND
    assert result.at_end.exposure.transition_ticks == 20 * SECOND
    assert result.resource_drained_tick == result.observation_end_tick == 160 * SECOND
