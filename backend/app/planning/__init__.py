"""Frozen ABC baseline, greedy 0/2/8 swap plans and before-shift relocation (01 §9, ADR 0016).

Public API (pure functions over contract models and plain mappings, ready for a later API):

- `PlanningGeometry.from_layout(layout)`: exact picker-graph distances and slot costs.
- `build_frozen_abc(layout, baseline, training_visits)`: deterministic ABC assignment.
- `plan_swaps(PlanningInputs, budget)` / `plan_budgets(PlanningInputs)`: plan artifacts.
- `apply_plan(baseline, plan, layout)`: candidate assignment; `verify_plan(plan, layout)`.
"""

from app.planning.abc import build_frozen_abc
from app.planning.apply import apply_plan, assignment_hash
from app.planning.errors import PlanningInputError
from app.planning.geometry import PlanningGeometry
from app.planning.greedy import (
    DEFAULT_BUDGETS,
    MAX_PAIRS_PER_ITERATION,
    SHORTLIST_SIZE,
    PlanningInputs,
)
from app.planning.models import (
    PairEvaluation,
    PlanArtifact,
    RelocationAction,
    RelocationSchedule,
    SwapSelection,
    TransferRecord,
)
from app.planning.plan import plan_budgets, plan_swaps
from app.planning.routes import SwapEvaluation, SwapRoute, WorkerRates, evaluate_swap
from app.planning.verify import verify_plan

__all__ = [
    "DEFAULT_BUDGETS",
    "MAX_PAIRS_PER_ITERATION",
    "SHORTLIST_SIZE",
    "PairEvaluation",
    "PlanArtifact",
    "PlanningGeometry",
    "PlanningInputError",
    "PlanningInputs",
    "RelocationAction",
    "RelocationSchedule",
    "SwapEvaluation",
    "SwapRoute",
    "SwapSelection",
    "TransferRecord",
    "WorkerRates",
    "apply_plan",
    "assignment_hash",
    "build_frozen_abc",
    "evaluate_swap",
    "plan_budgets",
    "plan_swaps",
    "verify_plan",
]
