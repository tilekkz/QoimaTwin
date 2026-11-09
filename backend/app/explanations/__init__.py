"""Optional Mercury advisory explanations for completed comparison artifacts."""

from app.explanations.errors import ExplanationError
from app.explanations.facts import extract_comparison_facts
from app.explanations.models import (
    ComparisonFacts,
    ExplanationResult,
    Fact,
    Observation,
    Provenance,
)
from app.explanations.prompt import PROMPT_VERSION, explanation_cache_key
from app.explanations.service import explain_comparison
from app.explanations.settings import MercurySettings

__all__ = [
    "PROMPT_VERSION",
    "ComparisonFacts",
    "ExplanationError",
    "ExplanationResult",
    "Fact",
    "MercurySettings",
    "Observation",
    "Provenance",
    "explain_comparison",
    "explanation_cache_key",
    "extract_comparison_facts",
]
