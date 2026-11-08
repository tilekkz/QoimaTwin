"""Spawn-safe dispatch to real materialization, forecast, planning and comparison modules."""

from __future__ import annotations

import os
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path

import jsonschema

from app.api.context import Job, Json, job_bundle, stored_assignment
from app.data.scenario_materializer import materialize
from app.errors import AppError, InvalidInputError
from app.storage.artifacts import ArtifactStore


@dataclass(frozen=True)
class WorkResult:
    payload: Json
    worker_pid: int


def execute_job(job: Job) -> WorkResult:
    from app.api.planning_jobs import compare_job, plan_job
    from app.v3.api_light_worker import light_job
    from app.v3.api_manual_worker import manual_job

    handlers = {
        "materialize": materialize_job,
        "forecast": forecast_job,
        "plans": plan_job,
        "compare": compare_job,
        "manual-v3": manual_job,
        "light-v3": light_job,
    }
    try:
        return WorkResult(handlers[job.kind](job), os.getpid())
    except AppError:
        raise
    except jsonschema.ValidationError as exc:
        raise InvalidInputError(f"input schema: {exc.message}") from exc
    except ValueError as exc:
        raise InvalidInputError(str(exc)) from exc


def _history_bytes() -> bytes:
    from app.data.history import history_artifact

    return history_artifact().csv_bytes


def materialize_job(job: Job) -> Json:
    store, bundle = ArtifactStore(Path(job.store_root)), job_bundle(job)
    assignment_id = job.payload.get("assignment_id", job.assignment_id)
    stored_assignment(store, assignment_id, bundle.layout)
    result = materialize(job.payload["profile"], job.payload["horizon_s"], bundle.config)
    scenario_id = store.put_json("scenarios", result.scenario.model_dump(mode="json"))
    history_id = store.put_bytes("histories", _history_bytes())
    return {
        "status": "passed",
        "scenario_id": scenario_id,
        "history_id": history_id,
        "assignment_id": assignment_id,
        "scenario_name": result.scenario.scenario_id,
        "horizon_s": result.scenario.horizon_s,
        "shortened_run": result.scenario.horizon_s < 3600,
        "orders": len(result.scenario.orders),
        "receipts": len(result.scenario.receipts),
    }


def forecast_job(job: Job) -> Json:
    forecast = import_module("app.forecast")
    store = ArtifactStore(Path(job.store_root))
    history_id = job.payload["history_id"]
    store.read_bytes("histories", history_id)  # verify bytes before a file-based parser reads them
    history = forecast.read_csv(store.path("histories", history_id))
    snapshot = forecast.fit_forecast(history, job.payload.get("model", "mean28"))
    identifier = store.put_json("forecasts", snapshot.semantic_dict())
    return {
        "status": "passed",
        "forecast_id": identifier,
        "source_history_id": history_id,
        "forecast": snapshot.to_dict(),
    }
