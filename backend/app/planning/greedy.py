"""Greedy 0/2/8 swap planner on the surrogate J (01 §9, ADR 0016).

J = sum(expected_visits * mean_home_roundtrip_m / walk_speed) + relocation_labor_s.
Pure inputs only: layout, config, baseline assignment, training and expected visit mappings.
There is deliberately no scenario or test-order argument: a plan is fixed before test.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations

from app.contracts.assignment import Assignment
from app.contracts.base import exact
from app.contracts.config import SimulationConfig
from app.contracts.layout import Layout
from app.planning.abc import active_lots
from app.planning.errors import PlanningInputError
from app.planning.geometry import PlanningGeometry
from app.planning.models import IterationRecord, PairEvaluation, ShortlistEntry
from app.planning.routes import SwapEvaluation, evaluate_swap
from app.planning.visits import exact_visits

SHORTLIST_SIZE = 32
MAX_PAIRS_PER_ITERATION = 496
DEFAULT_BUDGETS = (0, 2, 8)
MAX_BUDGET = SHORTLIST_SIZE // 2


@dataclass(frozen=True, slots=True)
class PlanningInputs:
    """Expected visits must already be scaled to the experiment horizon."""

    layout: Layout
    config: SimulationConfig
    baseline_assignment: Assignment
    training_visits: Mapping[str, float]
    expected_visits: Mapping[str, float]
    forecast_id: str


@dataclass(frozen=True, slots=True)
class Candidate:
    sku_a: str
    sku_b: str
    swap: SwapEvaluation
    gross_s: Fraction

    @property
    def net_s(self) -> Fraction:
        return self.gross_s - self.swap.labor_s

    def evaluation(self) -> PairEvaluation:
        return PairEvaluation(
            sku_a=self.sku_a,
            sku_b=self.sku_b,
            slot_a=self.swap.slot_a,
            slot_b=self.swap.slot_b,
            gross_gain_s=float(self.gross_s),
            relocation_labor_s=float(self.swap.labor_s),
            net_gain_s=float(self.net_s),
        )


@dataclass(slots=True)
class PlanningState:
    inputs: PlanningInputs
    geo: PlanningGeometry
    slot_of: dict[str, str]
    expected: dict[str, Fraction]
    training: dict[str, Fraction]
    speed: Fraction
    swap_cache: dict[tuple[str, str], SwapEvaluation]

    @classmethod
    def prepare(cls, inputs: PlanningInputs, geo: PlanningGeometry | None) -> PlanningState:
        geo = geo or PlanningGeometry.from_layout(inputs.layout)
        baseline = inputs.baseline_assignment
        _check_layouts(inputs, geo)
        active_lots(baseline)
        skus = list(baseline.active_assignment.values())
        for slot in baseline.active_assignment:
            geo.slot_cost(slot)
        return cls(
            inputs=inputs,
            geo=geo,
            slot_of=baseline.slot_of(),
            expected=exact_visits(inputs.expected_visits, skus, "expected_visits"),
            training=exact_visits(inputs.training_visits, skus, "training_visits"),
            speed=exact(inputs.config.walk_speed_mps),
            swap_cache={},
        )

    def visit_j(self, slot_of: Mapping[str, str]) -> Fraction:
        total = sum(
            (visits * self.geo.slot_cost(slot_of[sku]) for sku, visits in self.expected.items()),
            Fraction(0),
        )
        return total / self.speed

    def candidate(self, sku_a: str, sku_b: str) -> Candidate:
        slot_a, slot_b = self.slot_of[sku_a], self.slot_of[sku_b]
        key = (slot_a, slot_b)
        if key not in self.swap_cache:
            self.swap_cache[key] = evaluate_swap(self.geo, self.inputs.config, slot_a, slot_b)
        cost_a, cost_b = self.geo.slot_cost(slot_a), self.geo.slot_cost(slot_b)
        gross = (self.expected[sku_a] - self.expected[sku_b]) * (cost_a - cost_b) / self.speed
        return Candidate(sku_a, sku_b, self.swap_cache[key], gross)


def _check_layouts(inputs: PlanningInputs, geo: PlanningGeometry) -> None:
    versions = {
        inputs.layout.layout_version,
        inputs.config.layout_version,
        inputs.baseline_assignment.layout_version,
        geo.layout_version,
    }
    if len(versions) != 1:
        raise PlanningInputError(f"layout versions disagree: {sorted(versions)}")
    if not inputs.forecast_id:
        raise PlanningInputError("forecast_id must not be empty")


def check_budget(budget: int) -> None:
    if isinstance(budget, bool) or not isinstance(budget, int) or not 0 <= budget <= MAX_BUDGET:
        raise PlanningInputError(f"budget must be an integer in [0, {MAX_BUDGET}], got {budget}")


def shortlist(state: PlanningState) -> tuple[ShortlistEntry, ...]:
    """Up to 32 SKUs by |expected - training rescaled to the expected total|, ties by SKU."""
    total_training = sum(state.training.values(), Fraction(0))
    total_expected = sum(state.expected.values(), Fraction(0))
    scale = total_expected / total_training if total_training else Fraction(0)
    rows = []
    for sku, expected in state.expected.items():
        baseline_load = state.training[sku] * scale
        rows.append((-abs(expected - baseline_load), sku, expected, baseline_load))
    rows.sort()
    return tuple(
        ShortlistEntry(
            sku_id=sku,
            expected_visits=float(expected),
            baseline_load=float(load),
            abs_load_change=float(-negative),
        )
        for negative, sku, expected, load in rows[:SHORTLIST_SIZE]
    )


def greedy_select(
    state: PlanningState, skus: Sequence[str], budget: int
) -> tuple[list[tuple[int, Candidate]], list[IterationRecord], Candidate | None]:
    """Best positive net gain each iteration over untouched SKUs; ties by (sku_a, sku_b)."""
    pairs = list(combinations(sorted(skus), 2))
    if len(pairs) > MAX_PAIRS_PER_ITERATION:
        raise PlanningInputError(f"{len(pairs)} pairs exceed {MAX_PAIRS_PER_ITERATION}")
    touched: set[str] = set()
    chosen: list[tuple[int, Candidate]] = []
    records: list[IterationRecord] = []
    for iteration in range(1, budget + 1):
        open_pairs = [(a, b) for a, b in pairs if a not in touched and b not in touched]
        if not open_pairs:
            break
        options = [state.candidate(a, b) for a, b in open_pairs]
        best = min(options, key=lambda c: (-c.net_s, c.sku_a, c.sku_b))
        selected = best.net_s > 0
        records.append(
            IterationRecord(
                iteration=iteration,
                evaluated_pairs=len(open_pairs),
                best=best.evaluation(),
                selected=selected,
            )
        )
        if not selected:
            return chosen, records, best
        chosen.append((iteration, best))
        touched.update((best.sku_a, best.sku_b))
    return chosen, records, None
