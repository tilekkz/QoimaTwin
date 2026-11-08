"""Declared downtime blocks new admission but cannot cancel actual paid custody."""

from dataclasses import replace

from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.staff_registry import compile_staff_registry
from tests.v3.test_coordinator_fixtures import staffing_profile
from tests.v3.test_light_flow_fixtures import hand_orders
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor
from tests.v3.test_staff_registry_fixtures import registry_document


def test_break_start_during_admitted_pick_reports_violation_without_dropping_job() -> None:
    profile = staffing_profile()
    flow = replace(profile.world.receipts.flow, orders=hand_orders(1))
    document = registry_document()
    document["unavailability"] = [
        {
            "actor_id": "P01",
            "start_tick": 10 * SECOND,
            "end_tick": 25 * SECOND,
            "reason": "common_break",
        }
    ]
    profile = replace(
        profile,
        intents=(),
        registry=compile_staff_registry(document),
        world=replace(profile.world, receipts=replace(profile.world.receipts, flow=flow)),
    )
    result = CoordinatorEngine(profile, receipt_conveyor()).run(200 * SECOND, 240 * SECOND)
    assert result.at_end.orders[0].shipped_tick == 192_170_000
    worker = next(w for w in result.at_end.workers if w.actor_id == "P01")
    assert worker.paid_ticks == 20 * SECOND and worker.node == "H"
    assert result.staffing_status == "violated"
    assert [(v.tick, v.actor_id, v.reason) for v in result.constraint_violations] == [
        (10 * SECOND, "P01", "PRIMARY_BREAK_NOT_CLEAN")
    ]


def test_helper_waits_for_primary_paid_return_despite_common_break_already_started() -> None:
    profile = staffing_profile()
    order = replace(hand_orders(1)[0], arrival_tick=55 * SECOND)
    flow = replace(profile.world.receipts.flow, orders=(order,))
    profile = replace(
        profile, world=replace(profile.world, receipts=replace(profile.world.receipts, flow=flow))
    )
    result = CoordinatorEngine(profile, receipt_conveyor()).run(260 * SECOND, 300 * SECOND)
    role = next(r for r in result.at_end.roles if r.actor_id == "P12")
    # Deposit68 + belt30.915448 + primary approach2/pack3/clear1/return2.
    assert role.departed_tick == 106_915_448
    assert role.activated_tick == 112_915_448 and role.restored_tick == 160 * SECOND
    assert result.at_end.orders[0].shipped_tick == 247_170_000
    assert result.staffing_status == "violated"
    assert any(v.actor_id == "K06" and v.tick == 100 * SECOND for v in result.constraint_violations)


def test_initial_actor_availability_is_not_overridden_by_cross_training() -> None:
    profile = staffing_profile()
    flow = profile.world.receipts.flow
    flow = replace(
        flow,
        actors=tuple(
            replace(a, available_tick=110 * SECOND) if a.actor_id == "P12" else a
            for a in flow.actors
        ),
    )
    profile = replace(
        profile, world=replace(profile.world, receipts=replace(profile.world.receipts, flow=flow))
    )
    result = CoordinatorEngine(profile, receipt_conveyor()).run(200 * SECOND, 200 * SECOND)
    role = next(r for r in result.at_end.roles if r.actor_id == "P12")
    assert (role.departed_tick, role.activated_tick, role.restored_tick) == (
        110 * SECOND,
        116 * SECOND,
        160 * SECOND,
    )
    assert result.staffing_status == "valid"
