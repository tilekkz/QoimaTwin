"""Plans alone never establish an observed N4 demonstration."""

from dataclasses import replace

import pytest

from app.v3.coordinator_pair_models import IncomparableCoordinatorPair
from app.v3.coordinator_pair_rules import require_same_materialized_world, require_scenario_plan
from tests.v3.test_coordinator_multi_fixtures import multi_profile


def test_n4_requires_two_existing_distinct_pickers_and_stations() -> None:
    baseline = multi_profile(candidate=False)
    candidate = multi_profile(candidate=True)
    with pytest.raises(IncomparableCoordinatorPair, match="TWO_DISTINCT_PICKER_HELPERS"):
        require_scenario_plan(baseline, replace(candidate, intents=candidate.intents[:1]), "N4")
    duplicate = replace(candidate.intents[1], actor_id=candidate.intents[0].actor_id)
    with pytest.raises(IncomparableCoordinatorPair, match="TWO_DISTINCT_PICKER_HELPERS"):
        require_scenario_plan(
            baseline,
            replace(candidate, intents=(candidate.intents[0], duplicate)),
            "N4",
        )


def test_n4_baseline_cannot_hide_a_previous_role_plan() -> None:
    candidate = multi_profile(candidate=True)
    with pytest.raises(IncomparableCoordinatorPair, match="N4_BASELINE_ROLE_PLAN_MUST_BE_EMPTY"):
        require_scenario_plan(candidate, candidate, "N4")


def test_declared_restore_target_cannot_substitute_for_actual_home() -> None:
    baseline = multi_profile(candidate=False)
    candidate = multi_profile(candidate=True)
    wrong = replace(candidate.intents[0], restore_node="H12")
    with pytest.raises(IncomparableCoordinatorPair, match="RETURN_TO_EXISTING_ACTOR_HOME"):
        require_scenario_plan(
            baseline,
            replace(candidate, intents=(wrong, candidate.intents[1])),
            "N4",
        )


def test_materialized_timing_drift_is_detected_even_with_the_same_registry() -> None:
    baseline = multi_profile(candidate=False)
    candidate = multi_profile(candidate=True)
    require_same_materialized_world(baseline, candidate)
    receipt = candidate.world.receipts
    flow = replace(
        receipt.flow, times=replace(receipt.flow.times, pack=receipt.flow.times.pack + 1)
    )
    changed = replace(
        candidate, world=replace(candidate.world, receipts=replace(receipt, flow=flow))
    )
    assert changed.registry.registry_common_hash == baseline.registry.registry_common_hash
    with pytest.raises(IncomparableCoordinatorPair, match="MATERIALIZED_PHYSICAL_INPUT_DRIFT"):
        require_same_materialized_world(baseline, changed)
