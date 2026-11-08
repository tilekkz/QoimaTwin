"""Full physical A/B identity: only a validated role plan may differ."""

from copy import deepcopy
from typing import Any

from app.storage.canonical_json import parse_json
from app.v3.conveyor_models import ConveyorSource
from app.v3.coordinator_pair_models import IncomparableCoordinatorPair, PreparedCoordinatorPair
from app.v3.coordinator_pair_rules import (
    require_same_materialized_world,
    require_scenario_plan,
    scenario_name,
)
from app.v3.coordinator_profile import (
    CompiledCoordinatorProfile,
    compile_coordinator_profile,
    validate_compiled_coordinator,
)
from app.v3.input_models import V3Bundle


def prepare_coordinator_pair(
    bundle: V3Bundle,
    conveyor: ConveyorSource,
    baseline_document: Any,
    candidate_document: Any,
    *,
    scenario: object,
) -> PreparedCoordinatorPair:
    name = scenario_name(scenario)
    baseline = compile_coordinator_profile(bundle, conveyor, baseline_document)
    candidate = compile_coordinator_profile(bundle, conveyor, candidate_document)
    for compiled in (baseline, candidate):
        validate_compiled_coordinator(compiled, conveyor)
    left = _neutral(bundle, conveyor, baseline)
    right = _neutral(bundle, conveyor, candidate)
    if left.frozen_bytes != right.frozen_bytes:
        raise IncomparableCoordinatorPair("PHYSICAL_COMMON_INPUT_DRIFT")
    require_same_materialized_world(baseline.profile, candidate.profile)
    require_scenario_plan(baseline.profile, candidate.profile, name)
    if name == "N0" and baseline.frozen_bytes != candidate.frozen_bytes:
        raise IncomparableCoordinatorPair("N0_REQUIRES_IDENTICAL_FULL_INPUTS")
    return PreparedCoordinatorPair(name, baseline, candidate, left.input_hash)


def _neutral(
    bundle: V3Bundle,
    conveyor: ConveyorSource,
    compiled: CompiledCoordinatorProfile,
) -> CompiledCoordinatorProfile:
    frozen = parse_json(compiled.frozen_bytes)
    if not isinstance(frozen, dict) or not isinstance(frozen.get("choices"), dict):
        raise ValueError("Verified coordinator input has no strict choices object")
    choices = deepcopy(frozen["choices"])
    choices["role_intents"] = []
    # Failure is intentionally propagated. An invalid neutral world has no common hash.
    return compile_coordinator_profile(bundle, conveyor, choices)
