"""Co-located role changes have actual arrival facts and zero paid movement, not fake operations."""

from dataclasses import replace

from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.coordinator_run import build_coordinator_run
from app.v3.coordinator_run_inputs import freeze_hand_inputs
from tests.v3.test_coordinator_fixtures import staffing_profile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor


def test_zero_distance_roles_restore_without_invented_positive_paid_operations() -> None:
    profile = staffing_profile()
    homes = {"P11": "ST05", "P12": "PACK"}
    flow = profile.world.receipts.flow
    flow = replace(
        flow, actors=tuple(replace(a, home=homes.get(a.actor_id, a.home)) for a in flow.actors)
    )
    profile = replace(
        profile,
        world=replace(profile.world, receipts=replace(profile.world.receipts, flow=flow)),
        intents=tuple(replace(i, restore_node=homes[i.actor_id]) for i in profile.intents),
    )
    outcome = CoordinatorEngine(profile, receipt_conveyor()).run(200 * SECOND, 200 * SECOND)
    inputs = freeze_hand_inputs(profile, receipt_conveyor(), 200 * SECOND, 200 * SECOND)
    run = build_coordinator_run(inputs, outcome)
    assert all(event.kind != "operation_started" for event in outcome.events)
    assert {view.activated_tick for view in outcome.at_end.roles} == {100 * SECOND}
    assert {view.restored_tick for view in outcome.at_end.roles} == {154 * SECOND, 156 * SECOND}
    assert run["metrics"]["at_end"]["labor"]["role_transition_paid_ticks"] == 0
