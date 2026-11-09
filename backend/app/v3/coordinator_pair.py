"""Source-bound paired N0/N4 entry point; no hand-input or proxy scenario fallback."""

from typing import Any

from app.v3.conveyor_models import ConveyorSource
from app.v3.coordinator_pair_execute import _execute_pair
from app.v3.coordinator_pair_inputs import prepare_coordinator_pair
from app.v3.coordinator_pair_models import CoordinatorPairResult
from app.v3.input_models import V3Bundle

__all__ = ["compare_coordinator_profiles", "prepare_coordinator_pair"]


def compare_coordinator_profiles(
    bundle: V3Bundle,
    conveyor: ConveyorSource,
    baseline_document: Any,
    candidate_document: Any,
    *,
    scenario: object,
) -> CoordinatorPairResult:
    prepared = prepare_coordinator_pair(
        bundle,
        conveyor,
        baseline_document,
        candidate_document,
        scenario=scenario,
    )
    return _execute_pair(
        prepared.baseline,
        prepared.candidate,
        conveyor,
        prepared.scenario,
        prepared.common_input_hash,
        "source_bound_coordinator_profile",
    )
