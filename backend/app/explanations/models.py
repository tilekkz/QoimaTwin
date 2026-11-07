"""Local explanation types, separate from shared simulation contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

type Provenance = Literal["synthetic", "synthetic_fixture", "historical_partial_baskets", "unknown"]


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, allow_inf_nan=False)


class Fact(Frozen):
    fact_id: str
    value: float | int | bool | str | None


class ComparisonFacts(Frozen):
    provenance: Provenance = "unknown"
    window_semantics: str = (
        "at_horizon: counts/cycles [0,H); at_end: counts/cycles inclusive of end; "
        "labor: [0,side cutoff_s) in each window; end cutoffs can differ by side. "
        "labor = TRAVEL + BUSY_SERVICE; net savings subtract pre-shift relocation once."
    )
    items: tuple[Fact, ...]


class Observation(Frozen):
    text: str = Field(min_length=1, max_length=1500)
    fact_ids: tuple[str, ...] = Field(min_length=1, max_length=16)


class GeneratedObservations(Frozen):
    observations: tuple[Observation, ...] = Field(min_length=1, max_length=8)


class ExplanationResult(Frozen):
    comparison_id: str
    facts: ComparisonFacts
    observations: tuple[Observation, ...]
    model: str
    prompt_version: str
    cache_key: str
    ai_generated: Literal[True] = True
    advisory: str = (
        "AI-generated advisory observations; numeric facts remain authoritative. "
        "Known citations do not prove every prose claim true. No performance guarantee."
    )
