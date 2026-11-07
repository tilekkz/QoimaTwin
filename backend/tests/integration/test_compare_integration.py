"""API seams of compare_slotting: run callback, forecast binding and relocation semantics."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import pytest

import app.comparison.compare as compare_module
from app.comparison import ComparisonInputError, compare_slotting
from app.contracts.config import SimulationConfig
from app.contracts.layout import Layout
from app.contracts.loader import ContractBundle
from app.exporter.identity import fingerprint
from app.planning import PlanArtifact, apply_plan, plan_swaps
from app.simulation.context import RunInputs
from app.simulation.engine import Engine, RunOutcome
from app.storage.canonical_json import sha256_hex
from tests.builders import run_inputs, scenario
from tests.planning_support import forecast_semantics, two_sku_inputs

pytestmark = pytest.mark.integration


def _orders(sku: str, quantity: int = 1) -> list[dict[str, Any]]:
    return [
        {
            "order_id": f"O{i:03d}",
            "arrival_s": 30 * i,
            "lines": [{"sku_id": sku, "quantity": quantity}],
        }
        for i in range(3)
    ]


def _setup(
    bundle: ContractBundle,
    contracts_dir: Path,
    layout: Layout,
    config: SimulationConfig,
    *,
    budget: int = 2,
    orders: list[dict[str, Any]] | None = None,
) -> tuple[RunInputs, PlanArtifact]:
    semantics = forecast_semantics()
    planning = dataclasses.replace(
        two_sku_inputs(layout, config, expected={"SKU_X": 0.0, "SKU_Y": 10.0}),
        forecast_id=sha256_hex(semantics),
    )
    plan = plan_swaps(planning, budget=budget)
    base = run_inputs(bundle, contracts_dir, scenario(orders or _orders("SKU_Y"), horizon_s=600))
    baseline = dataclasses.replace(
        base,
        assignment=planning.baseline_assignment,
        experiment_type="slotting",
        forecast_snapshot=semantics,
    )
    return baseline, plan


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Engine, RunOutcome]] = []

    def __call__(self, variant: str, engine: Engine, outcome: RunOutcome) -> None:
        self.calls.append((variant, engine, outcome))


def test_callback_receives_the_two_compared_engines_once(
    bundle: ContractBundle,
    contracts_dir: Path,
    layout: Layout,
    config: SimulationConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[Engine] = []

    class CountingEngine(Engine):
        def __init__(self, inputs: RunInputs, *, check_invariants: bool = False) -> None:
            assert check_invariants
            super().__init__(inputs, check_invariants=check_invariants)
            created.append(self)

    monkeypatch.setattr(compare_module, "Engine", CountingEngine)
    baseline, plan = _setup(bundle, contracts_dir, layout, config)
    recorder = _Recorder()
    result = compare_slotting(baseline, plan, on_run=recorder)
    assert [variant for variant, _, _ in recorder.calls] == ["baseline", "candidate"]
    assert len(created) == 2
    assert [engine for _, engine, _ in recorder.calls] == created
    base_engine, cand_engine = created
    assert len(base_engine.ctx.recorder.events) == result.baseline.event_count
    assert len(cand_engine.ctx.recorder.events) == result.candidate.event_count
    for (_, _, outcome), side in zip(
        recorder.calls, (result.baseline, result.candidate), strict=True
    ):
        assert outcome.status.value == side.outcome.status
    relocation = cand_engine.ctx.inputs.relocation_json()
    assert relocation is not None
    assert relocation.sha256 == plan.plan_id
    assert base_engine.ctx.inputs.relocation_plan is None
    assert "engine" not in result.model_dump_json().lower()


def test_callback_sees_partial_outcomes(
    bundle: ContractBundle, contracts_dir: Path, layout: Layout, config: SimulationConfig
) -> None:
    # 3 orders x 1000 units of SKU_Y exceed the 2000 units on its pick face.
    orders = _orders("SKU_Y", quantity=1000)
    baseline, plan = _setup(bundle, contracts_dir, layout, config, orders=orders)
    recorder = _Recorder()
    compare_slotting(baseline, plan, on_run=recorder)
    assert [o.status.value for _, _, o in recorder.calls] == ["partial", "partial"]


def test_callback_failure_propagates(
    bundle: ContractBundle, contracts_dir: Path, layout: Layout, config: SimulationConfig
) -> None:
    baseline, plan = _setup(bundle, contracts_dir, layout, config)

    def fail(variant: str, engine: Engine, outcome: RunOutcome) -> None:
        raise OSError(f"publish {variant} failed")

    with pytest.raises(OSError, match="publish baseline failed"):
        compare_slotting(baseline, plan, on_run=fail)


def test_compare_binds_forecast_and_relocation_semantics(
    bundle: ContractBundle, contracts_dir: Path, layout: Layout, config: SimulationConfig
) -> None:
    baseline, plan = _setup(bundle, contracts_dir, layout, config, budget=0)
    result = compare_slotting(baseline, plan)
    assert result.forecast_snapshot_sha256 == sha256_hex(forecast_semantics())
    base_hashes, cand_hashes = result.baseline.input_hashes, result.candidate.input_hashes
    assert base_hashes["forecast_snapshot"] == cand_hashes["forecast_snapshot"]
    assert base_hashes["relocation_plan"] == sha256_hex(None)
    assert cand_hashes["relocation_plan"] == plan.plan_id
    assert result.semantic_identical  # budget 0: other identity, same event semantics


def test_compare_keeps_caller_candidate_forecast(
    bundle: ContractBundle, contracts_dir: Path, layout: Layout, config: SimulationConfig
) -> None:
    baseline, plan = _setup(bundle, contracts_dir, layout, config)
    candidate = dataclasses.replace(
        baseline,
        assignment=apply_plan(baseline.assignment, plan, layout),
        relocation_plan=plan.model_dump(mode="json"),
    )
    result = compare_slotting(baseline, plan, candidate_inputs=candidate)
    assert result.candidate.input_hashes == fingerprint(candidate)["hashes"]


def test_compare_rejects_plan_for_another_forecast(
    bundle: ContractBundle, contracts_dir: Path, layout: Layout, config: SimulationConfig
) -> None:
    baseline, plan = _setup(bundle, contracts_dir, layout, config)
    other = dataclasses.replace(baseline, forecast_snapshot=forecast_semantics(visits_y=11.0))
    with pytest.raises(ComparisonInputError, match="forecast"):
        compare_slotting(other, plan)


def test_compare_rejects_different_forecasts_between_runs(
    bundle: ContractBundle, contracts_dir: Path, layout: Layout, config: SimulationConfig
) -> None:
    baseline, plan = _setup(bundle, contracts_dir, layout, config)
    candidate = dataclasses.replace(
        baseline,
        assignment=apply_plan(baseline.assignment, plan, layout),
        relocation_plan=plan.model_dump(mode="json"),
        forecast_snapshot=forecast_semantics(model="hgb"),
    )
    with pytest.raises(ComparisonInputError, match="forecast_snapshot"):
        compare_slotting(baseline, plan, candidate_inputs=candidate)


def test_compare_rejects_wrong_relocation_semantics(
    bundle: ContractBundle, contracts_dir: Path, layout: Layout, config: SimulationConfig
) -> None:
    baseline, plan = _setup(bundle, contracts_dir, layout, config)
    candidate = dataclasses.replace(
        baseline, assignment=apply_plan(baseline.assignment, plan, layout)
    )
    with pytest.raises(ComparisonInputError, match="relocation"):
        compare_slotting(baseline, plan, candidate_inputs=candidate)
    with_plan = dataclasses.replace(baseline, relocation_plan=plan.model_dump(mode="json"))
    with pytest.raises(ComparisonInputError, match="relocation"):
        compare_slotting(with_plan, plan)
