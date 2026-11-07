from __future__ import annotations

from typing import cast

import pytest

from app.explanations import ExplanationError, extract_comparison_facts


def test_allowlist_and_windows(comparison: dict[str, object]) -> None:
    facts = extract_comparison_facts(comparison, provenance="synthetic")
    values = {fact.fact_id: fact.value for fact in facts.items}
    assert values["at_horizon.net_labor_saved_all_roles_s"] == 2.0
    assert values["at_end.net_labor_saved_all_roles_s"] == 2.0
    assert values["baseline.end_s"] == 110.0
    assert "PRIVATE" not in facts.model_dump_json()
    assert facts.provenance == "synthetic"
    assert "[0,H)" in facts.window_semantics
    assert "inclusive" in facts.window_semantics


@pytest.mark.parametrize("side", ["baseline", "candidate"])
@pytest.mark.parametrize("termination", ["deadlock", "max_drain", "unfulfilled_inventory"])
def test_partial_outcome_and_provenance_facts(
    comparison: dict[str, object], side: str, termination: str
) -> None:
    side_data = cast(dict[str, object], comparison[side])
    outcome = cast(dict[str, object], side_data["outcome"])
    outcome.update(status="partial", termination=termination)
    outcome["termination_reasons"] = [termination, "unfulfilled_inventory"]
    outcome["error_message"] = "PRIVATE raw error"
    facts = extract_comparison_facts(comparison, provenance="historical_partial_baskets")
    values = {fact.fact_id: fact.value for fact in facts.items}
    assert values[f"{side}.outcome.status"] == "partial"
    assert values[f"{side}.outcome.termination"] == termination
    assert values[f"{side}.outcome.termination_reasons.0"] == termination
    assert values[f"{side}.outcome.termination_reasons.1"] == "unfulfilled_inventory"
    other = "candidate" if side == "baseline" else "baseline"
    assert values[f"{other}.outcome.status"] == "complete"
    assert values[f"{other}.outcome.termination"] == "drained"
    assert values["at_end.net_labor_saved_all_roles_s"] == 2.0
    assert facts.provenance == "historical_partial_baskets"
    assert "PRIVATE" not in facts.model_dump_json()


@pytest.mark.parametrize("side", ["baseline", "candidate"])
@pytest.mark.parametrize("status", ["failed", "running", "unknown", None])
def test_reject_nonusable_outcome(comparison: dict[str, object], side: str, status: object) -> None:
    outcome = cast(dict[str, object], cast(dict[str, object], comparison[side])["outcome"])
    outcome["status"] = status
    with pytest.raises(ExplanationError, match="invalid_facts"):
        extract_comparison_facts(comparison)


@pytest.mark.parametrize(
    "change",
    [
        {"termination": None},
        {"termination": "PRIVATE unknown"},
        {"termination_reasons": ["PRIVATE unknown"]},
        {"termination_reasons": "PRIVATE"},
    ],
)
def test_reject_unknown_termination_without_echo(
    comparison: dict[str, object], change: dict[str, object]
) -> None:
    outcome = cast(dict[str, object], cast(dict[str, object], comparison["candidate"])["outcome"])
    outcome.update(change)
    with pytest.raises(ExplanationError, match="invalid_facts") as caught:
        extract_comparison_facts(comparison)
    assert "PRIVATE" not in str(caught.value)


@pytest.mark.parametrize(
    "change",
    [
        {"at_end": None},
        {"swaps": True},
        {"relocation_labor_s": float("nan")},
        {"artifact_version": "unknown"},
        {"baseline": {"outcome": {"status": "running"}}},
    ],
)
def test_reject_invalid_source(comparison: dict[str, object], change: dict[str, object]) -> None:
    comparison.update(change)
    with pytest.raises(ExplanationError, match="invalid_facts"):
        extract_comparison_facts(comparison)
