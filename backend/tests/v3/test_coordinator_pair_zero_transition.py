"""Prewritten zero-distance role evidence: actual state events, no invented paid travel."""

from dataclasses import replace

from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.coordinator_models import CoordinatorProfile
from app.v3.coordinator_pair_evidence import helper_evidence
from app.v3.coordinator_run import build_coordinator_run
from app.v3.coordinator_run_inputs import freeze_hand_inputs
from tests.v3.test_coordinator_multi_fixtures import multi_profile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor


def _co_located_helpers() -> CoordinatorProfile:
    profile = multi_profile(candidate=True)
    flow = profile.world.receipts.flow
    homes = {"P11": "ST05", "P12": "PACK"}
    flow = replace(
        flow,
        actors=tuple(replace(a, home=homes.get(a.actor_id, a.home)) for a in flow.actors),
    )
    return replace(
        profile,
        world=replace(profile.world, receipts=replace(profile.world.receipts, flow=flow)),
        intents=tuple(replace(i, restore_node=homes[i.actor_id]) for i in profile.intents),
    )


def test_zero_distance_roles_need_actual_completion_events_without_paid_operations() -> None:
    profile, conveyor = _co_located_helpers(), receipt_conveyor()
    inputs = freeze_hand_inputs(profile, conveyor, 200 * SECOND, 400 * SECOND)
    outcome = CoordinatorEngine(profile, conveyor).run(200 * SECOND, 400 * SECOND)
    build_coordinator_run(inputs, outcome)
    evidence = helper_evidence(profile, outcome)
    assert all(row["demonstrated"] for row in evidence)
    assert [row["transition_paid_ticks"] for row in evidence] == [0, 0]
    assert [row["packing_paid_ticks"] for row in evidence] == [4 * SECOND, 4 * SECOND]
    assert [row["activated_tick"] for row in evidence] == [100 * SECOND, 100 * SECOND]
    assert [row["restored_tick"] for row in evidence] == [156 * SECOND, 154 * SECOND]
    assert not any(
        e.operation is not None and e.operation.kind in {"role_outward", "role_return"}
        for e in outcome.events
    )
    missing = replace(
        outcome,
        events=tuple(
            e for e in outcome.events if not (e.kind == "role_restored" and e.actor_id == "P11")
        ),
    )
    assert [row["demonstrated"] for row in helper_evidence(profile, missing)] == [False, True]
