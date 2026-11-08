"""Actual shared-clock staffing microseconds and paid paths from independent hand arithmetic."""

from dataclasses import replace

from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.coordinator_models import CoordinatorSnapshot
from tests.v3.test_coordinator_fixtures import staffing_profile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor


def test_real_role_transitions_keep_24_workers_and_observe_calendar_after_goods_complete() -> None:
    profile = staffing_profile()
    engine = CoordinatorEngine(profile, receipt_conveyor())
    outcome = engine.run(200 * SECOND, 220 * SECOND)
    assert outcome.status == "complete" and outcome.staffing_status == "valid"
    assert outcome.business_complete_tick == 0
    assert outcome.resource_drained_tick == 160 * SECOND
    assert outcome.observation_end_tick == 200 * SECOND
    assert len(outcome.at_end.workers) == len(engine.workers) == 24
    assert outcome.at_end.stock == outcome.checkpoints[0].stock
    assert not outcome.at_end.leases and not engine.station_bindings
    roles = {r.intent_id: r for r in outcome.at_end.roles}
    assert (
        roles["I11"].departed_tick,
        roles["I11"].activated_tick,
        roles["I11"].restored_tick,
    ) == (100 * SECOND, 104 * SECOND, 160 * SECOND)
    assert (
        roles["I12"].departed_tick,
        roles["I12"].activated_tick,
        roles["I12"].restored_tick,
    ) == (100 * SECOND, 106 * SECOND, 160 * SECOND)
    workers = {w.actor_id: w for w in outcome.at_end.workers}
    assert workers["P11"].paid_ticks == 8 * SECOND
    assert workers["P12"].paid_ticks == 12 * SECOND
    assert workers["P11"].node == "H11" and workers["P12"].node == "H12"
    assert not outcome.constraint_violations


def test_actual_role_exposure_has_100_extra_pack_and_20_paid_transition_seconds() -> None:
    profile = staffing_profile()
    baseline = CoordinatorEngine(replace(profile, intents=()), receipt_conveyor()).run(
        200 * SECOND, 220 * SECOND
    )
    candidate = CoordinatorEngine(profile, receipt_conveyor()).run(200 * SECOND, 220 * SECOND)
    base, actual = baseline.at_horizon.exposure, candidate.at_horizon.exposure
    assert dict(base.role_ticks)["pack"] == 1080 * SECOND  # 6*200 -2*60
    assert dict(actual.role_ticks)["pack"] == 1180 * SECOND
    assert actual.transition_ticks == 20 * SECOND
    assert actual.unavailable_ticks == 120 * SECOND
    assert (
        sum(v for _, v in actual.role_ticks) + actual.transition_ticks + actual.unavailable_ticks
        == 24 * 200 * SECOND
    )
    assert baseline.resource_drained_tick == 0
    assert baseline.observation_end_tick == 200 * SECOND


def test_h105_capture_clips_motion_without_future_arrival_or_restoration() -> None:
    engine = CoordinatorEngine(staffing_profile(), receipt_conveyor())
    outcome = engine.run(105 * SECOND, 105 * SECOND)
    assert outcome.status == "partial" and outcome.resource_drained_tick is None
    view = outcome.at_horizon
    assert isinstance(view, CoordinatorSnapshot) and view.tick == 105 * SECOND
    assert view.exposure.transition_ticks == 9 * SECOND
    assert dict(view.exposure.role_ticks)["pack"] == 621 * SECOND  # 600 +4*5 +1
    actors = {w.actor_id: w for w in view.workers}
    assert actors["P11"].node == "ST05" and actors["P11"].operation is None
    assert actors["P12"].node is None and actors["P12"].operation is not None
    assert actors["P12"].operation.planned_end_tick == 106 * SECOND
    assert all(r.restored_tick is None for r in view.roles)
    assert all(event.tick <= 105 * SECOND for event in outcome.events)


def test_completion_exactly_at160_precedes_primary_reavailability_without_overlap() -> None:
    result = CoordinatorEngine(staffing_profile(), receipt_conveyor()).run(
        160 * SECOND, 160 * SECOND
    )
    assert result.status == "complete"
    assert all(r.status == "restored" for r in result.at_end.roles)
    tick_events = [e.kind for e in result.events if e.tick == 160 * SECOND]
    assert tick_events.index("role_restored") < tick_events.index("availability_changed")
    assert all(v.available for v in result.at_end.actor_roles)
