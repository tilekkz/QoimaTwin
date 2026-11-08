"""Non-public analytical fixture seam; never accepted by a source CLI/API endpoint."""

from dataclasses import replace

from app.v3.conveyor_models import ConveyorSource
from app.v3.coordinator_models import CoordinatorProfile
from app.v3.coordinator_pair_execute import _execute_pair
from app.v3.coordinator_pair_models import CoordinatorPairResult, IncomparableCoordinatorPair
from app.v3.coordinator_pair_rules import (
    require_same_materialized_world,
    require_scenario_plan,
    scenario_name,
)
from app.v3.coordinator_run_inputs import freeze_hand_inputs


def compare_hand_coordinator_profiles(
    baseline: CoordinatorProfile,
    candidate: CoordinatorProfile,
    conveyor: ConveyorSource,
    horizon_tick: int,
    end_tick: int,
    *,
    scenario: object,
) -> CoordinatorPairResult:
    name = scenario_name(scenario)
    left = freeze_hand_inputs(baseline, conveyor, horizon_tick, end_tick)
    right = freeze_hand_inputs(candidate, conveyor, horizon_tick, end_tick)
    neutral_left = freeze_hand_inputs(
        replace(baseline, intents=()),
        conveyor,
        horizon_tick,
        end_tick,
    )
    neutral_right = freeze_hand_inputs(
        replace(candidate, intents=()),
        conveyor,
        horizon_tick,
        end_tick,
    )
    if neutral_left.frozen_bytes != neutral_right.frozen_bytes:
        raise IncomparableCoordinatorPair("PHYSICAL_COMMON_INPUT_DRIFT")
    require_same_materialized_world(baseline, candidate)
    require_scenario_plan(baseline, candidate, name)
    if name == "N0" and left.frozen_bytes != right.frozen_bytes:
        raise IncomparableCoordinatorPair("N0_REQUIRES_IDENTICAL_FULL_INPUTS")
    return _execute_pair(
        left,
        right,
        conveyor,
        name,
        neutral_left.input_hash,
        "analytical_fixture",
    )
