"""Input equality for a slotting comparison (01 §10, 05 §9).

Only the assignment and the paid relocation plan may differ. Layout, config (including
operations policies), actors, orders, receipts, initial stock quantities and the forecast
snapshot must hash equal. The baseline carries no relocation plan; the candidate carries the
compared plan, and a supplied forecast must be the one the plan was made from.
No failure schedule exists in v2 inputs (breakdowns are P1), so there is nothing else to match.
"""

from __future__ import annotations

from typing import Any

from app.comparison.errors import ComparisonInputError
from app.exporter.identity import fingerprint
from app.planning import PlanArtifact, PlanningInputError, assignment_hash, verify_plan
from app.simulation.context import RunInputs
from app.storage.canonical_json import sha256_hex

SHARED_HASHES = (
    "layout",
    "config",
    "actors",
    "orders",
    "receipts",
    "initial_inventory",
    "forecast_snapshot",
)
NO_PLAN_HASH = sha256_hex(None)
SHARED_FIELDS = (
    "scenario_id",
    "horizon_s",
    "experiment_type",
    "ticks_per_second",
    "engine_version",
)


def validate_slotting_pair(
    baseline: RunInputs, candidate: RunInputs, plan: PlanArtifact
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return both fingerprints; raise ComparisonInputError on any forbidden difference."""
    if baseline.experiment_type != "slotting":
        raise ComparisonInputError(
            f"experiment_type must be slotting, got {baseline.experiment_type}"
        )
    first, second = fingerprint(baseline), fingerprint(candidate)
    for key in SHARED_HASHES:
        if first["hashes"][key] != second["hashes"][key]:
            raise ComparisonInputError(f"{key} hash differs between baseline and candidate")
    for key in SHARED_FIELDS:
        if first[key] != second[key]:
            raise ComparisonInputError(f"{key} differs between baseline and candidate")
    if assignment_hash(baseline.assignment) != plan.baseline_assignment_hash:
        raise ComparisonInputError("baseline assignment is not the plan's baseline")
    if assignment_hash(candidate.assignment) != plan.final_assignment_hash:
        raise ComparisonInputError("candidate assignment is not the plan's final assignment")
    _check_semantics(first, second, plan)
    _check_plan(baseline, plan, first["ticks_per_second"])
    return first, second


def _check_semantics(first: dict[str, Any], second: dict[str, Any], plan: PlanArtifact) -> None:
    """Baseline: no relocation; candidate: exactly this plan; forecast: the plan's own."""
    if first["hashes"]["relocation_plan"] != NO_PLAN_HASH:
        raise ComparisonInputError("baseline must not carry a relocation plan")
    if second["hashes"]["relocation_plan"] != plan.plan_id:
        raise ComparisonInputError("candidate relocation_plan semantics are not the compared plan")
    forecast = first["hashes"]["forecast_snapshot"]
    if forecast != NO_PLAN_HASH and forecast != plan.forecast_id:
        raise ComparisonInputError(
            f"plan was made for forecast {plan.forecast_id}, but the supplied forecast "
            f"snapshot hashes to {forecast}"
        )


def _check_plan(baseline: RunInputs, plan: PlanArtifact, tps: int) -> None:
    params = plan.parameters
    config = baseline.config
    if (params.walk_speed_mps, params.take_or_place_s) != (
        config.walk_speed_mps,
        config.relocation_take_or_place_s,
    ):
        raise ComparisonInputError("plan worker rates differ from the run config")
    if plan.relocation.ticks_per_second != tps:
        raise ComparisonInputError("plan and run use different time grids")
    try:
        verify_plan(plan, baseline.layout)
    except PlanningInputError as exc:
        raise ComparisonInputError(f"invalid plan: {exc}") from exc
