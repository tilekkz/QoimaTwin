"""Explicit, bounded field selection from a completed qoima-compare-v1 artifact."""

from __future__ import annotations

from collections.abc import Mapping

from app.explanations.errors import ExplanationError
from app.explanations.metrics import metric_facts
from app.explanations.models import ComparisonFacts, Fact, Provenance
from app.explanations.validation import mapping, number

NUMBERS = ("relocation_labor_s", "relocation_distance_m")
SAVINGS = (
    "gross_labor_saved_picker_s",
    "gross_labor_saved_all_roles_s",
    "net_labor_saved_picker_s",
    "net_labor_saved_all_roles_s",
    "blocked_delta_s",
    "wait_resource_delta_s",
)
TERMINATIONS = ("drained", "deadlock", "max_drain", "unfulfilled_inventory", "error")


def _outcome_facts(outcome: Mapping[str, object], side: str) -> list[Fact]:
    result: list[Fact] = []
    for key, allowed in (("status", ("complete", "partial")), ("termination", TERMINATIONS)):
        value = outcome.get(key)
        if not isinstance(value, str) or value not in allowed:
            raise ExplanationError("invalid_facts")
        result.append(Fact(fact_id=f"{side}.outcome.{key}", value=value))
    if "termination_reasons" in outcome:
        reasons = outcome["termination_reasons"]
        if not isinstance(reasons, list) or len(reasons) > len(TERMINATIONS):
            raise ExplanationError("invalid_facts")
        for index, reason in enumerate(reasons):
            if not isinstance(reason, str) or reason not in TERMINATIONS:
                raise ExplanationError("invalid_facts")
            result.append(Fact(fact_id=f"{side}.outcome.termination_reasons.{index}", value=reason))
    return result


def _windows(source: Mapping[str, object]) -> list[Fact]:
    result: list[Fact] = []
    for name in ("at_horizon", "at_end"):
        window = mapping(source.get(name))
        if window.get("window") != name:
            raise ExplanationError("invalid_facts")
        result.extend(number(window, key, f"{name}.") for key in SAVINGS)
        verdict = window.get("verdict")
        if verdict not in ("improved", "worsened", "unchanged"):
            raise ExplanationError("invalid_facts")
        result.append(Fact(fact_id=f"{name}.verdict", value=verdict))
        for side in ("baseline", "candidate"):
            labor = mapping(window.get(side))
            for key in ("cutoff_s", "total_labor_s"):
                result.append(number(labor, key, f"{name}.{side}."))
    return result


def extract_comparison_facts(
    comparison: Mapping[str, object], *, provenance: Provenance = "unknown"
) -> ComparisonFacts:
    """Pass artifact.model_dump(mode='json'); provenance comes from server-owned scenario data."""
    if (
        comparison.get("artifact_version") != "qoima-compare-v1"
        or comparison.get("experiment_type") != "slotting"
    ):
        raise ExplanationError("invalid_facts")
    items = [number(comparison, name) for name in NUMBERS]
    for name in ("budget_swaps", "swaps"):
        if type(comparison.get(name)) is not int:
            raise ExplanationError("invalid_facts")
        items.append(number(comparison, name))
    for name in ("is_noop", "semantic_identical"):
        value = comparison.get(name)
        if not isinstance(value, bool):
            raise ExplanationError("invalid_facts")
        items.append(Fact(fact_id=name, value=value))
    for side in ("baseline", "candidate"):
        side_data = mapping(comparison.get(side))
        outcome = mapping(side_data.get("outcome"))
        items.extend(_outcome_facts(outcome, side))
        for key in ("horizon_s", "end_s"):
            items.append(number(outcome, key, f"{side}."))
        items.extend(metric_facts(side_data, side))
    return ComparisonFacts(provenance=provenance, items=tuple(items + _windows(comparison)))
