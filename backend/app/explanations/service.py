"""Optional synchronous service; never imports simulation, mutates artifacts or writes files."""

from __future__ import annotations

import httpx

from app.explanations.errors import ExplanationError
from app.explanations.models import ComparisonFacts, ExplanationResult
from app.explanations.prompt import PROMPT_VERSION, explanation_cache_key
from app.explanations.provider import request_observations
from app.explanations.settings import MercurySettings


def explain_comparison(
    comparison_id: str,
    facts: ComparisonFacts,
    *,
    settings: MercurySettings,
    client: httpx.Client | None = None,
) -> ExplanationResult:
    """Backend call only. Inject a trusted client/MockTransport, never HTTP client settings."""
    if settings.api_key is None or not settings.api_key.strip():
        raise ExplanationError("unavailable")
    if client is None:
        with httpx.Client(trust_env=False) as owned:
            generated = request_observations(owned, facts, settings)
    else:
        generated = request_observations(client, facts, settings)
    result = ExplanationResult(
        comparison_id=comparison_id,
        facts=facts,
        observations=generated.observations,
        model=settings.model,
        prompt_version=PROMPT_VERSION,
        cache_key=explanation_cache_key(comparison_id, facts, settings=settings),
    )
    partial = [
        fact.fact_id.removesuffix(".outcome.status")
        for fact in facts.items
        if fact.fact_id in ("baseline.outcome.status", "candidate.outcome.status")
        and fact.value == "partial"
    ]
    if partial:
        warning = " ".join(f"The {side} outcome is partial." for side in partial)
        return result.model_copy(
            update={
                "advisory": f"{result.advisory} {warning} A finished comparison does not establish "
                "complete simulation flow; order counts do not establish all flow completed."
            }
        )
    return result
