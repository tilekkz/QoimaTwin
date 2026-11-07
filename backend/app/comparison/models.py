"""JSON-ready baseline/candidate comparison artifact for Tilek's A/B view (ADR 0016).

No wall-clock timings are stored, so equal inputs give byte-equal artifacts.
"""

from __future__ import annotations

from typing import Any, Literal

from app.comparison.labor import LaborSummary
from app.contracts.base import FrozenModel

COMPARISON_ARTIFACT_VERSION = "qoima-compare-v1"
Verdict = Literal["improved", "worsened", "unchanged"]


class OutcomeView(FrozenModel):
    status: str
    termination: str
    horizon_s: float
    end_s: float


class RunSide(FrozenModel):
    """One simulated variant. input_hashes come from the current run fingerprint (ADR 0008)."""

    variant: Literal["baseline", "candidate"]
    assignment_id: str
    assignment_hash: str
    input_hashes: dict[str, str]
    outcome: OutcomeView
    event_count: int
    action_count: int
    events_sha256: str
    actions_sha256: str
    metrics: dict[str, Any]


class WindowComparison(FrozenModel):
    """net = baseline - candidate - relocation labor; picker and all roles shown separately."""

    window: Literal["at_horizon", "at_end"]
    baseline: LaborSummary
    candidate: LaborSummary
    gross_labor_saved_picker_s: float
    gross_labor_saved_all_roles_s: float
    net_labor_saved_picker_s: float
    net_labor_saved_all_roles_s: float
    blocked_delta_s: float
    wait_resource_delta_s: float
    verdict: Verdict


class ComparisonArtifact(FrozenModel):
    artifact_version: Literal["qoima-compare-v1"]
    comparison_id: str
    experiment_type: Literal["slotting"]
    scenario_id: str
    plan_id: str
    forecast_id: str
    forecast_snapshot_sha256: str | None
    budget_swaps: int
    swaps: int
    is_noop: bool
    relocation_labor_s: float
    relocation_labor_ticks: int
    relocation_distance_m: float
    baseline: RunSide
    candidate: RunSide
    at_horizon: WindowComparison
    at_end: WindowComparison
    semantic_identical: bool
    notes: tuple[str, ...]
