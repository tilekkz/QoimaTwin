"""Fresh profile/decision authentication and normal N1 execution in the existing worker."""

import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any

from app.api.context import Job
from app.api.errors import UnexpectedExecutionError
from app.errors import InvalidInputError
from app.storage.artifacts import ArtifactCorruption, ArtifactStore
from app.storage.canonical_json import canonical_bytes
from app.v3.api_coordinator_inputs import freeze_profile
from app.v3.api_forecast_relocation_inputs import (
    DOMAIN,
    ForecastRelocationRequest,
    UnknownForecastRelocation,
    load_profile,
    load_request,
    profile_snapshot,
    public_id,
    recipe_hash,
)
from app.v3.api_forecast_relocation_storage import checked, publish, response
from app.v3.api_forecast_relocation_validation import output_files, validate_output
from app.v3.api_offer_planning_inputs import public_id as offer_id
from app.v3.api_offer_planning_storage import checked as checked_offer
from app.v3.api_offer_planning_storage import response as offer_response
from app.v3.api_offer_planning_worker import planning_read_job
from app.v3.forecast_relocation_binding import prepare_forecast_relocation
from app.v3.forecast_relocation_cli import compare_forecast_relocation
from app.v3.forecast_relocation_models import ForecastRelocationChoices, ForecastRelocationInputs
from app.v3.offer_planning_cli_storage import put
from app.v3.workload_policy import fields


def _fresh_profile(
    store: ArtifactStore, source: Path, expected: str | None = None
) -> tuple[str, dict[str, Any]]:
    try:
        before = recipe_hash()
        compiled = freeze_profile(store, source)
        value = profile_snapshot(compiled.bundle_id, compiled.metadata)
        if value["recipe_sha256"] != before:
            raise ValueError("Allowlisted recipe changed during compilation")
        identifier = store.put_json("bundles", value)
        if expected is not None and identifier != expected:
            raise ValueError("Profile is not the current allowlisted source recipe")
        load_profile(store, identifier)
        return identifier, value
    except (ValueError, TypeError, KeyError, OSError, InvalidInputError) as exc:
        raise ArtifactCorruption("Current registered actual profile authentication failed") from exc


def profile_job(job: Job) -> dict[str, Any]:
    payload = fields(job.payload, {"source_root"})
    store = ArtifactStore(Path(job.store_root))
    identifier, value = _fresh_profile(store, Path(payload["source_root"]))
    return {
        "profiles": [
            dict(
                value,
                actual_profile_id=identifier,
                acknowledgement_required=True,
                engine_execution=False,
            )
        ]
    }


def _decision(job: Job, store: ArtifactStore, request_id: str) -> bytes:
    identifier = offer_id(request_id)
    result = planning_read_job(
        replace(
            job,
            kind="offer-planning-read-v3",
            payload={"planning_id": identifier, "artifact_id": None},
        )
    )
    index, raw = checked_offer(store, identifier)
    if canonical_bytes(result) != canonical_bytes(offer_response(index)):
        raise ArtifactCorruption("Planning authority changed while binding decision")
    return raw["decision.json"]


def _bound(
    job: Job, store: ArtifactStore, body: ForecastRelocationRequest, attempt: Path | None = None
) -> ForecastRelocationInputs:
    _fresh_profile(store, Path(job.payload["source_root"]), body.actual_profile_id)
    profile, registered = load_profile(store, body.actual_profile_id)
    common = store.read_bytes("run_files", registered["frozen_inputs"])
    decision = _decision(job, store, body.offer_request_id)
    if attempt is not None:
        put(attempt, "decision.json", decision)
        put(attempt, "common-inputs.json", common)
        put(attempt, "profile.json", canonical_bytes(profile))
    try:
        return prepare_forecast_relocation(
            decision, common, ForecastRelocationChoices(body.job_id, body.arrival_tick)
        )
    except (ValueError, TypeError, KeyError) as exc:
        raise InvalidInputError(
            "Forecast decision and registered actual common inputs do not bind"
        ) from exc


def relocation_job(job: Job) -> dict[str, Any]:
    payload = fields(job.payload, {"request_id", "source_root"})
    store = ArtifactStore(Path(job.store_root))
    identifier = public_id(payload["request_id"])
    if store.path("runs", identifier).exists():
        return relocation_read_job(
            replace(
                job,
                kind="forecast-relocation-read-v3",
                payload={
                    "run_id": identifier,
                    "artifact_id": None,
                    "source_root": payload["source_root"],
                },
            )
        )
    body = load_request(store, payload["request_id"])
    root = store.root / "forecast-relocation-v3-evidence"
    root.mkdir(parents=True, exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix="attempt-", dir=root))
    try:
        put(attempt, "request.json", store.read_bytes("bundles", payload["request_id"]))
        value = _bound(job, store, body, attempt)
        compare_forecast_relocation(value, attempt / "output")
        raw = output_files(attempt / "output")
        result = validate_output(raw, value)
        return publish(store, payload["request_id"], raw, result)
    except Exception as exc:
        put(
            attempt,
            "failure.json",
            canonical_bytes(
                dict(
                    domain=DOMAIN,
                    status="failed",
                    exception_type=type(exc).__name__,
                    partial_outputs_preserved=True,
                )
            ),
        )
        if isinstance(exc, (InvalidInputError, ArtifactCorruption)):
            raise
        raise UnexpectedExecutionError(
            "Forecast relocation execution or publication failed"
        ) from exc


def relocation_read_job(job: Job) -> dict[str, Any]:
    payload = fields(job.payload, {"run_id", "artifact_id", "source_root"})
    store = ArtifactStore(Path(job.store_root))
    index, raw = checked(store, payload["run_id"])
    selected = [row for row in index["files"] if row["sha256"] == payload["artifact_id"]]
    if payload["artifact_id"] is not None and not selected:
        raise UnknownForecastRelocation("File is not a member of this forecast relocation")
    try:
        value = _bound(job, store, load_request(store, index["request_id"]))
        expected = validate_output(raw, value)
        if canonical_bytes(expected) != canonical_bytes(index["result"]):
            raise ValueError("Saved result differs from authenticated native comparison")
        if selected:
            return {"body": raw[selected[0]["path"]], "media_type": "application/json"}
        return response(index)
    except (ValueError, TypeError, KeyError, OSError, InvalidInputError) as exc:
        raise ArtifactCorruption("Stored forecast relocation authority is invalid") from exc
