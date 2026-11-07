"""Planner and comparison honesty gates P1 and P6 (05 §9) on small explicit scenarios.

Engine runs use check_invariants=True. Expectations are relations from the spec (equal
inputs give equal semantic output; a forecast-chosen plan that worsens test stays reported),
never numbers copied from engine output.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import pytest

from app.comparison import ComparisonInputError, compare_slotting
from app.contracts.config import SimulationConfig
from app.contracts.layout import Layout
from app.contracts.loader import ContractBundle
from app.exporter.identity import fingerprint
from app.planning import apply_plan, plan_swaps
from app.simulation.context import RunInputs
from tests.builders import run_inputs, scenario
from tests.planning_support import two_sku_inputs

pytestmark = pytest.mark.acceptance


def _orders(sku: str, count: int) -> list[dict[str, Any]]:
    return [
        {"order_id": f"O{i:03d}", "arrival_s": 30 * i, "lines": [{"sku_id": sku, "quantity": 1}]}
        for i in range(count)
    ]


def _baseline(
    bundle: ContractBundle, contracts_dir: Path, assignment_inputs: Any, sku: str
) -> RunInputs:
    base = run_inputs(bundle, contracts_dir, scenario(_orders(sku, 4), horizon_s=600))
    return dataclasses.replace(
        base, assignment=assignment_inputs.baseline_assignment, experiment_type="slotting"
    )


def test_p1_noop_keeps_assignment_and_semantic_output(
    bundle: ContractBundle, contracts_dir: Path, layout: Layout, config: SimulationConfig
) -> None:
    planning = two_sku_inputs(layout, config, expected={"SKU_X": 0.0, "SKU_Y": 10.0})
    plan = plan_swaps(planning, budget=0)
    result = compare_slotting(_baseline(bundle, contracts_dir, planning, "SKU_Y"), plan)
    assert result.is_noop
    assert result.relocation_labor_s == 0
    assert result.baseline.assignment_hash == result.candidate.assignment_hash
    assert result.semantic_identical
    assert result.baseline.events_sha256 == result.candidate.events_sha256
    assert result.baseline.actions_sha256 == result.candidate.actions_sha256
    assert result.baseline.metrics == result.candidate.metrics
    for window in (result.at_horizon, result.at_end):
        assert window.net_labor_saved_all_roles_s == 0
        assert window.net_labor_saved_picker_s == 0
        assert window.verdict == "unchanged"


def test_p6_forecast_plan_that_worsens_test_is_reported(
    bundle: ContractBundle, contracts_dir: Path, layout: Layout, config: SimulationConfig
) -> None:
    # Forecast: SKU_Y (on the dear slot) is hot, so the plan swaps it to the cheap slot.
    planning = two_sku_inputs(layout, config, expected={"SKU_X": 0.0, "SKU_Y": 10.0})
    plan = plan_swaps(planning, budget=2)
    assert not plan.is_noop
    plan_id_before_test = plan.plan_id
    # Test day: only SKU_X is ordered, and the plan moved it to the dear slot.
    result = compare_slotting(_baseline(bundle, contracts_dir, planning, "SKU_X"), plan)
    assert result.plan_id == plan_id_before_test
    assert result.relocation_labor_s == 328
    assert result.relocation_labor_ticks == 328 * 3_000_000  # 336 m / 1.2 + 6 * 8 s
    for window in (result.at_horizon, result.at_end):
        assert window.gross_labor_saved_picker_s < 0
        assert window.net_labor_saved_picker_s < 0
        assert window.net_labor_saved_all_roles_s < 0
        assert window.verdict == "worsened"
        assert window.net_labor_saved_all_roles_s == pytest.approx(
            window.baseline.total_labor_s - window.candidate.total_labor_s - 328
        )
    assert result.baseline.outcome.status == "complete"
    assert result.candidate.outcome.status == "complete"


def test_forecast_plan_that_matches_test_improves_picker_labor(
    bundle: ContractBundle, contracts_dir: Path, layout: Layout, config: SimulationConfig
) -> None:
    planning = two_sku_inputs(layout, config, expected={"SKU_X": 0.0, "SKU_Y": 10.0})
    plan = plan_swaps(planning, budget=2)
    result = compare_slotting(_baseline(bundle, contracts_dir, planning, "SKU_Y"), plan)
    assert result.at_end.gross_labor_saved_picker_s > 0
    assert not result.semantic_identical
    data = result.model_dump(mode="json")
    assert data["comparison_id"] == result.comparison_id
    assert "wall" not in str(data).lower()


def test_compare_rejects_inputs_that_differ_beyond_assignment(
    bundle: ContractBundle, contracts_dir: Path, layout: Layout, config: SimulationConfig
) -> None:
    planning = two_sku_inputs(layout, config, expected={"SKU_X": 0.0, "SKU_Y": 10.0})
    plan = plan_swaps(planning, budget=2)
    baseline = _baseline(bundle, contracts_dir, planning, "SKU_Y")
    candidate = dataclasses.replace(
        baseline,
        assignment=apply_plan(baseline.assignment, plan, layout),
        scenario=scenario(_orders("SKU_Y", 3), horizon_s=600),
    )
    with pytest.raises(ComparisonInputError, match="orders"):
        compare_slotting(baseline, plan, candidate_inputs=candidate)
    slower = dataclasses.replace(
        candidate,
        scenario=baseline.scenario,
        config=baseline.config.model_copy(update={"pick_base_s": 7.0}),
    )
    with pytest.raises(ComparisonInputError, match="config"):
        compare_slotting(baseline, plan, candidate_inputs=slower)


def test_compare_rejects_candidate_assignment_not_from_plan(
    bundle: ContractBundle, contracts_dir: Path, layout: Layout, config: SimulationConfig
) -> None:
    planning = two_sku_inputs(layout, config, expected={"SKU_X": 0.0, "SKU_Y": 10.0})
    plan = plan_swaps(planning, budget=2)
    baseline = _baseline(bundle, contracts_dir, planning, "SKU_Y")
    with pytest.raises(ComparisonInputError, match="assignment"):
        compare_slotting(baseline, plan, candidate_inputs=baseline)


def test_plan_hashes_match_run_identity_hashes(
    bundle: ContractBundle, contracts_dir: Path, layout: Layout, config: SimulationConfig
) -> None:
    planning = two_sku_inputs(layout, config, expected={"SKU_X": 0.0, "SKU_Y": 10.0})
    plan = plan_swaps(planning, budget=2)
    baseline = _baseline(bundle, contracts_dir, planning, "SKU_Y")
    candidate = dataclasses.replace(
        baseline, assignment=apply_plan(baseline.assignment, plan, layout)
    )
    assert fingerprint(baseline)["hashes"]["assignment"] == plan.baseline_assignment_hash
    assert fingerprint(candidate)["hashes"]["assignment"] == plan.final_assignment_hash
    # A slot swap keeps the placement-independent stock hash (ADR 0008).
    assert (
        fingerprint(baseline)["hashes"]["initial_inventory"]
        == fingerprint(candidate)["hashes"]["initial_inventory"]
    )


def test_compare_rejects_plan_made_for_other_worker_rates(
    bundle: ContractBundle, contracts_dir: Path, layout: Layout, config: SimulationConfig
) -> None:
    slow = config.model_copy(update={"walk_speed_mps": 1.0})
    planning = two_sku_inputs(layout, slow, expected={"SKU_X": 0.0, "SKU_Y": 10.0})
    plan = plan_swaps(planning, budget=2)
    with pytest.raises(ComparisonInputError, match="rates"):
        compare_slotting(_baseline(bundle, contracts_dir, planning, "SKU_Y"), plan)
