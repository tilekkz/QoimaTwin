"""Baseline/candidate slotting comparison on one materialized scenario (01 §10, ADR 0016).

Both runs use the current Engine with check_invariants=True. Relocation happens before the
shift, so its labor is subtracted separately and the shift calendar is unchanged. A plan that
worsens the test outcome is reported as such; nothing is re-selected after seeing results.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from enum import Enum
from fractions import Fraction
from typing import Any, Literal

from app.comparison.errors import ComparisonInputError
from app.comparison.labor import LaborSummary, labor_breakdown
from app.comparison.models import (
    COMPARISON_ARTIFACT_VERSION,
    ComparisonArtifact,
    OutcomeView,
    RunSide,
    Verdict,
    WindowComparison,
)
from app.comparison.validation import validate_slotting_pair
from app.planning import PlanArtifact, PlanningInputError, apply_plan, assignment_hash
from app.simulation.context import RunInputs
from app.simulation.engine import Engine, RunOutcome
from app.simulation.metrics_summary import open_blocks, summary
from app.storage.canonical_json import sha256_hex

NOTES = (
    "labor = TRAVEL + BUSY_SERVICE; BLOCKED and WAIT_RESOURCE are reported separately",
    "relocation is before the shift on its own calendar; its labor is subtracted once",
    "the plan was fixed before the test run; a worse result is reported, not replaced",
    "run identity hashes for plan and forecast are attached by the run identity module",
)


Variant = Literal["baseline", "candidate"]
RunCallback = Callable[[str, Engine, RunOutcome], None]


@dataclasses.dataclass(frozen=True, slots=True)
class _Run:
    side: RunSide
    at_horizon: LaborSummary
    at_end: LaborSummary


def compare_slotting(
    baseline_inputs: RunInputs,
    plan: PlanArtifact,
    *,
    candidate_inputs: RunInputs | None = None,
    on_run: RunCallback | None = None,
) -> ComparisonArtifact:
    """Run baseline and candidate, then report labor at H and at end with relocation netted.

    `on_run(variant, engine, outcome)` is called exactly once per finished run ("baseline",
    then "candidate"), also for partial outcomes, so a caller can export the same engines.
    Its exceptions propagate. Engines are not kept in the returned artifact.
    """
    candidate_inputs = candidate_inputs or _candidate(baseline_inputs, plan)
    first, second = validate_slotting_pair(baseline_inputs, candidate_inputs, plan)
    base = _run("baseline", baseline_inputs, first, on_run)
    cand = _run("candidate", candidate_inputs, second, on_run)
    forecast = baseline_inputs.forecast_json()
    relocation = plan.relocation_labor_ticks
    tps = first["ticks_per_second"]
    data: dict[str, Any] = {
        "artifact_version": COMPARISON_ARTIFACT_VERSION,
        "comparison_id": "",
        "experiment_type": "slotting",
        "scenario_id": baseline_inputs.scenario.scenario_id,
        "plan_id": plan.plan_id,
        "forecast_id": plan.forecast_id,
        "forecast_snapshot_sha256": forecast.sha256 if forecast else None,
        "budget_swaps": plan.budget_swaps,
        "swaps": len(plan.selected_pairs),
        "is_noop": plan.is_noop,
        "relocation_labor_s": plan.relocation_labor_s,
        "relocation_labor_ticks": relocation,
        "relocation_distance_m": plan.relocation_distance_m,
        "baseline": base.side,
        "candidate": cand.side,
        "at_horizon": _window("at_horizon", base.at_horizon, cand.at_horizon, relocation, tps),
        "at_end": _window("at_end", base.at_end, cand.at_end, relocation, tps),
        "semantic_identical": _semantic_identical(base.side, cand.side),
        "notes": NOTES,
    }
    artifact = ComparisonArtifact.model_validate(data)
    content = artifact.model_dump(mode="json")
    content.pop("comparison_id")
    return artifact.model_copy(update={"comparison_id": sha256_hex(content)})


def _candidate(baseline: RunInputs, plan: PlanArtifact) -> RunInputs:
    try:
        assignment = apply_plan(baseline.assignment, plan, baseline.layout)
    except PlanningInputError as exc:
        raise ComparisonInputError(f"plan does not apply to the baseline: {exc}") from exc
    return dataclasses.replace(
        baseline, assignment=assignment, relocation_plan=plan.model_dump(mode="json")
    )


def _run(
    variant: Variant, inputs: RunInputs, fingerprint: dict[str, Any], on_run: RunCallback | None
) -> _Run:
    engine = Engine(inputs, check_invariants=True)
    outcome = engine.run()
    if on_run is not None:
        on_run(variant, engine, outcome)
    tps = engine.ctx.grid.ticks_per_second
    roles = {a.actor_id: a.role for a in inputs.actors.actors}
    blocks = open_blocks(engine)

    def labor(cutoff: int) -> LaborSummary:
        actions = engine.ctx.recorder.actions
        return labor_breakdown(actions, roles, open_blocks=blocks, cutoff_tick=cutoff, tps=tps)

    side = RunSide.model_validate(
        {
            "variant": variant,
            "assignment_id": inputs.assignment.assignment_id,
            "assignment_hash": assignment_hash(inputs.assignment),
            "input_hashes": dict(fingerprint["hashes"]),
            "outcome": _outcome(outcome, tps),
            "event_count": len(engine.ctx.recorder.events),
            "action_count": len(engine.ctx.recorder.actions),
            "events_sha256": _events_digest(engine),
            "actions_sha256": _actions_digest(engine),
            "metrics": _jsonable(summary(engine, outcome)),
        }
    )
    return _Run(side, labor(outcome.horizon_tick), labor(outcome.end_tick))


def _outcome(outcome: RunOutcome, tps: int) -> OutcomeView:
    return OutcomeView(
        status=outcome.status.value,
        termination=outcome.termination.value,
        horizon_s=float(Fraction(outcome.horizon_tick, tps)),
        end_s=float(Fraction(outcome.end_tick, tps)),
    )


def _window(
    name: str, base: LaborSummary, cand: LaborSummary, relocation: int, tps: int
) -> WindowComparison:
    def role_ticks(summary_: LaborSummary, role: str) -> int:
        entry = summary_.by_role.get(role)
        return entry.labor_ticks if entry else 0

    gross_picker = role_ticks(base, "picker") - role_ticks(cand, "picker")
    gross_all = base.labor_ticks - cand.labor_ticks
    net_all = gross_all - relocation
    return WindowComparison.model_validate(
        {
            "window": name,
            "baseline": base,
            "candidate": cand,
            "gross_labor_saved_picker_s": float(Fraction(gross_picker, tps)),
            "gross_labor_saved_all_roles_s": float(Fraction(gross_all, tps)),
            "net_labor_saved_picker_s": float(Fraction(gross_picker - relocation, tps)),
            "net_labor_saved_all_roles_s": float(Fraction(net_all, tps)),
            "blocked_delta_s": float(Fraction(base.blocked_ticks - cand.blocked_ticks, tps)),
            "wait_resource_delta_s": float(
                Fraction(base.wait_resource_ticks - cand.wait_resource_ticks, tps)
            ),
            "verdict": _verdict(net_all),
        }
    )


def _verdict(net_ticks: int) -> Verdict:
    if net_ticks > 0:
        return "improved"
    return "worsened" if net_ticks < 0 else "unchanged"


def _semantic_identical(base: RunSide, cand: RunSide) -> bool:
    return (base.events_sha256, base.actions_sha256, base.metrics) == (
        cand.events_sha256,
        cand.actions_sha256,
        cand.metrics,
    )


def _jsonable(value: Any) -> Any:
    """Plain JSON values for hashing; enums by value, Fractions as [numerator, denominator]."""
    if isinstance(value, Enum):
        return _jsonable(value.value)
    if isinstance(value, Fraction):
        return [value.numerator, value.denominator]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        items = sorted(value) if isinstance(value, (set, frozenset)) else value
        return [_jsonable(item) for item in items]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"cannot hash {type(value).__name__} in a run journal")


def _events_digest(engine: Engine) -> str:
    events = [
        [e.at_tick, int(e.phase), e.kind, e.entity_id, _jsonable(e.payload)]
        for e in engine.ctx.recorder.events
    ]
    return sha256_hex(events)


def _actions_digest(engine: Engine) -> str:
    actions = [
        [
            a.actor_id,
            a.state.value,
            a.operation,
            a.start_tick,
            a.end_tick,
            a.entity_id,
            _jsonable(a.pos),
            [[w.node_id, _jsonable(w.pos), w.at_tick] for w in a.waypoints],
        ]
        for a in engine.ctx.recorder.actions
    ]
    return sha256_hex(actions)
