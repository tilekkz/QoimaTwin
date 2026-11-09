"""Real planning adapters; only the declared horizon is exposed to forecast-based selection."""

from __future__ import annotations

import dataclasses
from importlib import import_module
from pathlib import Path

from app.api.context import Job, Json, job_bundle, stored_assignment
from app.api.publication import publish_run
from app.contracts.scenario import Scenario
from app.errors import InvalidInputError
from app.simulation.context import RunInputs
from app.simulation.engine import Engine, RunOutcome
from app.storage.artifacts import ArtifactStore


def _scaled_visits(forecast: Json, horizon_s: float) -> tuple[dict[str, float], dict[str, float]]:
    if (
        forecast.get("protocol") != "qoima-forecast-temporal-1"
        or forecast.get("full_day_s") != 28800
    ):
        raise InvalidInputError("unsupported forecast temporal protocol or daily units")
    scale = horizon_s / 28800
    training = {sku: value * scale for sku, value in forecast["training_visits_by_sku"].items()}
    expected = {
        sku: value * scale for sku, value in forecast["predictions"]["visits_by_sku"].items()
    }
    return training, expected


def plan_job(job: Job) -> Json:
    planning = import_module("app.planning")
    store, bundle = ArtifactStore(Path(job.store_root)), job_bundle(job)
    payload = job.payload
    scenario = Scenario.from_data(store.read_json("scenarios", payload["scenario_id"]))
    forecast = store.read_json("forecasts", payload["forecast_id"])
    assignment = stored_assignment(
        store, payload.get("assignment_id", job.assignment_id), bundle.layout
    )
    if scenario.layout_version != bundle.layout.layout_version:
        raise InvalidInputError("scenario layout differs from the active bundle")
    training, expected = _scaled_visits(forecast, scenario.horizon_s)
    baseline = planning.build_frozen_abc(bundle.layout, assignment, training)
    inputs = planning.PlanningInputs(
        bundle.layout, bundle.config, baseline, training, expected, payload["forecast_id"]
    )
    plan = planning.plan_swaps(inputs, payload["budget_swaps"])
    baseline_id = store.put_json("assignments", baseline.model_dump(mode="json"))
    candidate_id = store.put_json("assignments", plan.final_assignment.model_dump(mode="json"))
    envelope = {
        "bundle_id": job.bundle_id,
        "scenario_id": payload["scenario_id"],
        "forecast_id": payload["forecast_id"],
        "baseline_assignment_id": baseline_id,
        "candidate_assignment_id": candidate_id,
        "plan": plan.model_dump(mode="json"),
    }
    identifier = store.put_json("plans", envelope)
    return {"status": "passed", "plan_id": identifier, **envelope}


def compare_job(job: Job) -> Json:
    planning, comparison = import_module("app.planning"), import_module("app.comparison")
    store, bundle = ArtifactStore(Path(job.store_root)), job_bundle(job)
    envelope = store.read_json("plans", job.payload["plan_id"])
    if (
        envelope["bundle_id"] != job.bundle_id
        or envelope["scenario_id"] != job.payload["scenario_id"]
    ):
        raise InvalidInputError("plan does not belong to the requested scenario and input bundle")
    plan = planning.PlanArtifact.from_data(envelope["plan"])
    scenario = Scenario.from_data(store.read_json("scenarios", job.payload["scenario_id"]))
    assignment = stored_assignment(store, envelope["baseline_assignment_id"], bundle.layout)
    forecast = store.read_json("forecasts", envelope["forecast_id"])
    baseline = RunInputs(bundle.layout, bundle.config, bundle.actors, assignment, scenario)
    baseline = dataclasses.replace(baseline, forecast_snapshot=forecast)
    candidate = dataclasses.replace(
        baseline,
        assignment=planning.apply_plan(assignment, plan, bundle.layout),
        relocation_plan=plan.model_dump(mode="json"),
    )
    published: dict[str, str] = {}

    def on_run(side: str, engine: Engine, outcome: RunOutcome) -> None:
        if side not in {"baseline", "candidate"} or side in published:
            raise RuntimeError("comparison must publish each named side exactly once")
        published[side] = publish_run(
            store, engine, outcome, job.payload.get("output_format", "2.0")
        )

    result = comparison.compare_slotting(baseline, plan, candidate_inputs=candidate, on_run=on_run)
    if set(published) != {"baseline", "candidate"}:
        raise RuntimeError("comparison did not publish both run artifacts")
    data = result.model_dump(mode="json")
    identifier = store.put_json(
        "comparisons",
        {"comparison": data, "runs": published, "scenario_id": job.payload["scenario_id"]},
    )
    return {"status": "passed", "comparison_id": identifier, "comparison": data, "runs": published}
