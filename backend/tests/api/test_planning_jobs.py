"""Production planner adapters use forecast/day units and reject changed comparison inputs."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.api.context import ApiContext, Job
from app.api.planning_jobs import compare_job, plan_job
from app.api.worker import forecast_job
from app.data.scenario_materializer import materialize
from app.errors import InvalidInputError
from app.storage.artifacts import ArtifactStore
from tests.api.test_processor import _constant_history


def _plan_request(
    tmp_path: Path, contracts_dir: Path, *, empty: bool = False
) -> tuple[ApiContext, Job]:
    store = ArtifactStore(tmp_path)
    context = ApiContext.create(store, contracts_dir)
    history_id = store.put_bytes("histories", _constant_history())
    forecast = forecast_job(context.job("forecast", {"history_id": history_id, "model": "mean28"}))
    scenario = materialize("large-normal", 3600, context.bundle.config).scenario
    if empty:
        scenario = scenario.model_copy(update={"orders": (), "receipts": ()})
    scenario_id = store.put_json("scenarios", scenario.model_dump(mode="json"))
    request = context.job(
        "plans",
        {"scenario_id": scenario_id, "forecast_id": forecast["forecast_id"], "budget_swaps": 0},
    )
    return context, request


def test_real_zero_budget_plan_has_abc_baseline_and_scaled_visits(
    tmp_path: Path, contracts_dir: Path
) -> None:
    context, request = _plan_request(tmp_path, contracts_dir)
    result = plan_job(request)
    plan = result["plan"]
    assert plan["is_noop"] is True
    assert plan["budget_swaps"] == 0 and plan["selected_pairs"] == []
    assert plan["relocation_labor_s"] == 0
    baseline = context.store.read_json("assignments", result["baseline_assignment_id"])
    # 01 section9:200 active SKUs occupy200 of288 ground slots;88 remain empty.
    assert len(baseline["active_assignment"]) == 200
    assert len(baseline["empty_pickfaces"]) == 88
    assert {row["expected_visits"] for row in plan["shortlist"]} == {0.25}  # 2/day /8h
    assert context.store.read_json("plans", result["plan_id"])["plan"] == plan


def test_compare_rejects_different_stored_scenario_before_simulating(
    tmp_path: Path, contracts_dir: Path
) -> None:
    context, request = _plan_request(tmp_path, contracts_dir)
    result = plan_job(request)
    other = context.store.read_json("scenarios", request.payload["scenario_id"])
    other["scenario_id"] = "different-test"
    other_id = context.store.put_json("scenarios", other)
    with pytest.raises(InvalidInputError, match="does not belong"):
        compare_job(context.job("compare", {"scenario_id": other_id, "plan_id": result["plan_id"]}))


@pytest.mark.parametrize("output_format", ["2.0", "2.1-proposal"])
def test_real_empty_comparison_publishes_both_run_manifests(
    tmp_path: Path, contracts_dir: Path, output_format: str
) -> None:
    context, request = _plan_request(tmp_path, contracts_dir, empty=True)
    planned = plan_job(request)
    result = compare_job(
        context.job(
            "compare",
            {
                "scenario_id": request.payload["scenario_id"],
                "plan_id": planned["plan_id"],
                "output_format": output_format,
            },
        )
    )
    assert set(result["runs"]) == {"baseline", "candidate"}
    # Empty inputs and zero relocation imply zero active labor and zero net gain.
    assert result["comparison"]["at_horizon"]["net_labor_saved_all_roles_s"] == 0
    for run_id in result["runs"].values():
        manifest = context.store.read_reference("runs", run_id)
        assert manifest["run_id"] == run_id
        assert manifest["metrics"]["at_end"]["dispatched_total"] == 0
        if output_format == "2.1-proposal":
            assert manifest["contract_status"] == "proposal"
            assert manifest["event_chunks"] and manifest["snapshot_chunks"]
