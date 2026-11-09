"""Storage observations are projections of fully verified registered native results."""

import asyncio

from fastapi import FastAPI

from app.api.context import ApiContext
from app.api.models import ArtifactId
from app.storage.artifacts import ArtifactCorruption, ArtifactStore
from app.v3.api_coordinator_inputs import FrozenCoordinatorProfile
from app.v3.api_coordinator_readers import _request_context
from app.v3.api_coordinator_registry import CoordinatorRegistry
from app.v3.api_coordinator_replay import Registration
from app.v3.interface import Json
from app.v3.storage_fullness_publication import _fullness_from_context

READER_VERSION = "qoima-coordinator-storage-fullness-api-0.1.0"


def attach_fullness_route(
    app: FastAPI,
    context: ApiContext,
    registry: CoordinatorRegistry,
    registered: Registration,
) -> None:
    @app.get("/api/v3/coordinator-runs/{run_id}/storage-fullness")
    async def get_fullness(run_id: ArtifactId) -> Json:
        frozen = await registered(context, registry, run_id)
        return await asyncio.to_thread(storage_fullness, context.store, run_id, frozen)


def storage_fullness(
    store: ArtifactStore, identifier: str, frozen: FrozenCoordinatorProfile
) -> Json:
    context = _request_context(store, identifier, frozen)
    run = context.run()
    try:
        report = _fullness_from_context(context)
    except (ValueError, TypeError, KeyError, OSError) as exc:
        raise ArtifactCorruption("coordinator storage observation validation failed") from exc
    return {
        "reader_version": READER_VERSION,
        "run_id": identifier,
        "native_run_id": run["run_id"],
        "input_hash": run["input_hash"],
        "observed_until_tick": run["observed_until_tick"],
        "report": report,
    }
