"""Two actual coordinator instances; strict native publication precedes comparison claims."""

from app.storage.canonical_json import canonical_bytes
from app.v3.conveyor_models import ConveyorSource
from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.coordinator_pair_models import CoordinatorPairResult, PairScenario
from app.v3.coordinator_pair_report import report, scenario_evidence, side
from app.v3.coordinator_profile import CompiledCoordinatorProfile
from app.v3.coordinator_run import build_coordinator_run
from app.v3.coordinator_run_inputs import HandCoordinatorInputs

PairInput = CompiledCoordinatorProfile | HandCoordinatorInputs


def _execute_pair(
    baseline: PairInput,
    candidate: PairInput,
    conveyor: ConveyorSource,
    scenario: PairScenario,
    common_hash: str,
    scope: str,
) -> CoordinatorPairResult:
    # Only the validating source/hand preparation functions call this internal seam.
    before = CoordinatorEngine(baseline.profile, conveyor).run(
        baseline.horizon_tick,
        baseline.end_tick,
    )
    after = CoordinatorEngine(candidate.profile, conveyor).run(
        candidate.horizon_tick,
        candidate.end_tick,
    )
    baseline_run = build_coordinator_run(baseline, before)
    candidate_run = build_coordinator_run(candidate, after)
    demonstrated, evidence = scenario_evidence(scenario, candidate.profile, before, after)
    value = report(
        scenario,
        common_hash,
        scope,
        side(baseline_run, before),
        side(candidate_run, after),
        demonstrated,
        evidence,
    )
    return CoordinatorPairResult(
        canonical_bytes(value),
        canonical_bytes(baseline_run),
        canonical_bytes(candidate_run),
        baseline.frozen_bytes,
        candidate.frozen_bytes,
    )
