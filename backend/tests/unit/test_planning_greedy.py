"""Greedy 0/2/8 swap planner (01 §9, 05 §9 P3/P4/P5). Hand-arithmetic expectations only."""

from __future__ import annotations

import dataclasses
import inspect
from fractions import Fraction
from itertools import pairwise
from pathlib import Path

import pytest

from app.contracts.assignment import Assignment
from app.contracts.config import SimulationConfig
from app.contracts.layout import Layout
from app.planning import (
    MAX_PAIRS_PER_ITERATION,
    SHORTLIST_SIZE,
    PlanningGeometry,
    PlanningInputError,
    PlanningInputs,
    build_frozen_abc,
    evaluate_swap,
    plan_budgets,
    plan_swaps,
    verify_plan,
)
from tests.planning_support import CHEAP, DEAR, SWAP_LABOR_S, SWAP_ROUTE_M, two_sku_inputs


@pytest.fixture(scope="module")
def geometry(layout: Layout) -> PlanningGeometry:
    return PlanningGeometry.from_layout(layout)


def test_swap_route_both_orientations_follow_the_graph(
    geometry: PlanningGeometry, config: SimulationConfig
) -> None:
    swap = evaluate_swap(geometry, config, CHEAP, DEAR)
    assert swap.a_first.distance_m == SWAP_ROUTE_M
    assert swap.b_first.distance_m == SWAP_ROUTE_M
    assert swap.chosen is swap.a_first  # undirected graph: tie, pinned to A first
    assert swap.labor_s == SWAP_LABOR_S
    assert swap.a_first.stops == (
        "I02",
        "N_A01_Z16",
        "N_REL_BUFFER",
        "N_A12_Z34",
        "N_A01_Z16",
        "N_REL_BUFFER",
        "N_A12_Z34",
        "I02",
    )
    legs = [geometry.distance(a, b) for a, b in pairwise(swap.a_first.stops)]
    assert legs == [
        22,
        82,
        Fraction(29, 2),
        Fraction(135, 2),
        82,
        Fraction(29, 2),
        Fraction(107, 2),
    ]


def test_swap_on_one_service_node_still_visits_the_buffer(
    geometry: PlanningGeometry, config: SimulationConfig
) -> None:
    swap = evaluate_swap(geometry, config, "S_A12_B12_L_01", "S_A12_B12_R_01")
    assert swap.chosen.distance_m == 153
    assert swap.labor_s == Fraction(351, 2)


def test_one_profitable_swap_has_hand_computed_gain_and_j(
    layout: Layout, config: SimulationConfig
) -> None:
    # gross = (10 - 0) * (107 - 44) / 1.2 = 525 s; net = 525 - 328 = 197 s
    inputs = two_sku_inputs(layout, config, expected={"SKU_X": 0.0, "SKU_Y": 10.0})
    plan = plan_swaps(inputs, budget=2)
    assert not plan.is_noop
    (pair,) = plan.selected_pairs
    assert (pair.sku_a, pair.sku_b, pair.slot_a, pair.slot_b) == ("SKU_X", "SKU_Y", CHEAP, DEAR)
    assert pair.gross_gain_s == 525
    assert pair.relocation_labor_s == 328
    assert pair.net_gain_s == 197
    assert plan.relocation_labor_s == 328
    assert plan.relocation_distance_m == 336
    assert plan.predicted.baseline_j_s == pytest.approx(10 * 107 / 1.2)
    assert plan.predicted.candidate_visit_j_s == pytest.approx(10 * 44 / 1.2)
    assert plan.predicted.candidate_j_s == pytest.approx(10 * 44 / 1.2 + 328)
    assert plan.final_assignment.slot_of() == {"SKU_X": DEAR, "SKU_Y": CHEAP}


def test_p4_gain_below_relocation_cost_selects_noop(
    layout: Layout, config: SimulationConfig
) -> None:
    # gross = 6 * 63 / 1.2 = 315 s < 328 s relocation labor
    inputs = two_sku_inputs(layout, config, expected={"SKU_X": 0.0, "SKU_Y": 6.0})
    plan = plan_swaps(inputs, budget=8)
    assert plan.is_noop
    assert plan.noop_reason == "no_positive_net_gain"
    assert plan.selected_pairs == ()
    assert plan.relocation_labor_s == 0
    assert plan.final_assignment == inputs.baseline_assignment
    assert plan.best_rejected is not None
    assert plan.best_rejected.gross_gain_s == 315
    assert plan.best_rejected.net_gain_s == -13


def test_budget_zero_is_an_explicit_noop(layout: Layout, config: SimulationConfig) -> None:
    inputs = two_sku_inputs(layout, config, expected={"SKU_X": 0.0, "SKU_Y": 10.0})
    plan = plan_swaps(inputs, budget=0)
    assert plan.is_noop
    assert plan.noop_reason == "budget_zero"
    assert plan.relocation.transfers == ()
    assert plan.relocation.actions == ()


def test_planner_has_no_test_scenario_argument() -> None:
    params = set(inspect.signature(plan_swaps).parameters)
    fields = {f.name for f in dataclasses.fields(PlanningInputs)}
    assert not ({"scenario", "orders", "test_orders"} & (params | fields))


def test_plan_id_is_stable_and_depends_on_inputs(layout: Layout, config: SimulationConfig) -> None:
    inputs = two_sku_inputs(layout, config, expected={"SKU_X": 0.0, "SKU_Y": 10.0})
    reordered = dataclasses.replace(inputs, expected_visits={"SKU_Y": 10.0, "SKU_X": 0.0})
    first = plan_swaps(inputs, budget=2)
    assert first.plan_id == plan_swaps(reordered, budget=2).plan_id
    other = dataclasses.replace(inputs, expected_visits={"SKU_X": 0.0, "SKU_Y": 11.0})
    assert plan_swaps(other, budget=2).plan_id != first.plan_id
    renamed = dataclasses.replace(inputs, forecast_id="another-forecast")
    assert plan_swaps(renamed, budget=2).plan_id != first.plan_id
    assert first.model_dump(mode="json")["plan_id"] == first.plan_id


@pytest.fixture(scope="module")
def large_inputs(
    layout: Layout, config: SimulationConfig, contracts_dir: Path, geometry: PlanningGeometry
) -> PlanningInputs:
    example = Assignment.from_json_text((contracts_dir / "assignment.example.json").read_bytes())
    skus = sorted(example.active_assignment.values())
    training = {sku: float(1000 - i) for i, sku in enumerate(skus)}
    baseline = build_frozen_abc(layout, example, training, geometry=geometry)
    # Forecast flips demand: the 40 coldest SKUs become hottest; scaled to a smaller horizon.
    expected = {sku: training[sku] / 100 for sku in skus}
    for i, sku in enumerate(skus[-40:]):
        expected[sku] = 1000.0 + 100 * i
    return PlanningInputs(layout, config, baseline, training, expected, "forecast-large")


def test_p3_budgets_touch_disjoint_ground_skus(
    large_inputs: PlanningInputs, layout: Layout
) -> None:
    plans = plan_budgets(large_inputs)
    assert [p.budget_swaps for p in plans] == [0, 2, 8]
    ground = {s.slot_id for s in layout.slots if s.kind == "pickface"}
    for plan, limit in zip(plans, (0, 4, 16), strict=True):
        skus = [s for pair in plan.selected_pairs for s in (pair.sku_a, pair.sku_b)]
        assert len(skus) == len(set(skus)) == limit
        slots = {s for pair in plan.selected_pairs for s in (pair.slot_a, pair.slot_b)}
        assert slots <= ground
        assert all(pair.net_gain_s > 0 for pair in plan.selected_pairs)
        verify_plan(plan, layout)
    nets = [pair.net_gain_s for pair in plans[2].selected_pairs]
    assert nets == sorted(nets, reverse=True)


def test_shortlist_and_pair_limits(large_inputs: PlanningInputs) -> None:
    plan = plan_swaps(large_inputs, budget=8)
    assert SHORTLIST_SIZE == 32
    assert MAX_PAIRS_PER_ITERATION == 496
    assert len(plan.shortlist) == 32
    deltas = [(-entry.abs_load_change, entry.sku_id) for entry in plan.shortlist]
    assert deltas == sorted(deltas)
    assert plan.iterations[0].evaluated_pairs == 496
    assert all(it.evaluated_pairs <= 496 for it in plan.iterations)
    assert plan.iterations[1].evaluated_pairs == 435  # C(30, 2) after one disjoint pair


def test_shortlist_ties_break_by_sku_id(layout: Layout, config: SimulationConfig) -> None:
    inputs = two_sku_inputs(
        layout, config, expected={"SKU_X": 1.0, "SKU_Y": 1.0}, training={"SKU_X": 1, "SKU_Y": 1}
    )
    plan = plan_swaps(inputs, budget=2)
    assert [e.sku_id for e in plan.shortlist] == ["SKU_X", "SKU_Y"]


@pytest.mark.parametrize("budget", [-1, 17])
def test_rejects_bad_budget(layout: Layout, config: SimulationConfig, budget: int) -> None:
    inputs = two_sku_inputs(layout, config, expected={"SKU_X": 0.0, "SKU_Y": 10.0})
    with pytest.raises(PlanningInputError):
        plan_swaps(inputs, budget=budget)


def test_rejects_visits_for_unknown_skus(layout: Layout, config: SimulationConfig) -> None:
    inputs = two_sku_inputs(layout, config, expected={"SKU_X": 0.0, "SKU_Z": 10.0})
    with pytest.raises(PlanningInputError):
        plan_swaps(inputs, budget=2)
