"""Registered namespace3 runs share the existing owned calculation worker."""

import asyncio
from pathlib import Path
from typing import Annotated, cast

from fastapi import FastAPI, Query, Request, Response

from app.api.context import ApiContext, Json
from app.api.models import ArtifactId
from app.api.service import JobService
from app.errors import InvalidInputError
from app.storage.artifacts import ArtifactCorruption
from app.v3 import api_coordinator_readers as readers
from app.v3.api_coordinator_fullness import attach_fullness_route
from app.v3.api_coordinator_inputs import CoordinatorRequest, FrozenCoordinatorProfile
from app.v3.api_coordinator_registry import CoordinatorRegistry
from app.v3.api_coordinator_replay import attach_replay_route
from app.v3.settings import default_inputs

Tick = Annotated[str, Query(pattern=r"^(0|[1-9][0-9]*)$", max_length=20)]


def attach_coordinator_routes(app: FastAPI, context: ApiContext, source: Path | None) -> None:
    registry = CoordinatorRegistry(context.store, source or default_inputs())

    @app.get("/api/v3/coordinator-profiles")
    async def profiles() -> Json:
        frozen = await registry.get()
        metadata = await asyncio.to_thread(readers.profile_metadata, context.store, frozen)
        return {"profiles": [metadata]}

    @app.post("/api/v3/coordinator-runs")
    async def submit(body: CoordinatorRequest, request: Request) -> Json:
        frozen = await registry.get()
        metadata = await asyncio.to_thread(readers.profile_metadata, context.store, frozen)
        if any(getattr(body, k) != metadata[k] for k in ("layout_version", "source_revision")):
            raise InvalidInputError("coordinator registered profile source/layout mismatch")
        job = context.job("coordinator-v3", {"coordinator_bundle_id": frozen.bundle_id})
        result = await cast(JobService, request.app.state.jobs).submit_job(job, frozen.key())
        return await asyncio.to_thread(readers.verify_result, context.store, result, frozen)

    attach_reads(app, context, registry)
    attach_replay_route(app, context, registry, _read_registration)
    attach_fullness_route(app, context, registry, _read_registration)


def attach_reads(app: FastAPI, context: ApiContext, registry: CoordinatorRegistry) -> None:
    @app.get("/api/v3/coordinator-runs/{run_id}")
    async def get_status(run_id: ArtifactId) -> Json:
        return await asyncio.to_thread(
            readers.status,
            context.store,
            run_id,
            await _read_registration(context, registry, run_id),
        )

    @app.get("/api/v3/coordinator-runs/{run_id}/manifest")
    async def get_manifest(run_id: ArtifactId) -> Json:
        return await asyncio.to_thread(
            readers.manifest,
            context.store,
            run_id,
            await _read_registration(context, registry, run_id),
        )

    @app.get("/api/v3/coordinator-runs/{run_id}/files/{artifact_id}")
    async def get_file(run_id: ArtifactId, artifact_id: ArtifactId) -> Response:
        index, _ = await asyncio.to_thread(
            readers.verified_artifact,
            context.store,
            run_id,
            await _read_registration(context, registry, run_id),
        )
        raw = await asyncio.to_thread(readers.file_bytes, context.store, index, artifact_id)
        return Response(raw, media_type="application/json", headers={"ETag": f'"{artifact_id}"'})

    _attach_time_reads(app, context, registry)


def _attach_time_reads(app: FastAPI, context: ApiContext, registry: CoordinatorRegistry) -> None:
    @app.get("/api/v3/coordinator-runs/{run_id}/checkpoint")
    async def get_checkpoint(run_id: ArtifactId, tick: Tick) -> Json:
        return await asyncio.to_thread(
            readers.checkpoint,
            context.store,
            run_id,
            int(tick),
            await _read_registration(context, registry, run_id),
        )

    @app.get("/api/v3/coordinator-runs/{run_id}/events")
    async def get_events(run_id: ArtifactId, start_tick: Tick, end_tick: Tick) -> Json:
        return await asyncio.to_thread(
            readers.events,
            context.store,
            run_id,
            int(start_tick),
            int(end_tick),
            await _read_registration(context, registry, run_id),
        )


async def _read_registration(
    context: ApiContext,
    registry: CoordinatorRegistry,
    identifier: str,
) -> FrozenCoordinatorProfile:
    await asyncio.to_thread(readers.known_run_reference, context.store, identifier)
    try:
        return await registry.get()
    except (InvalidInputError, ValueError, TypeError, KeyError, OSError) as exc:
        raise ArtifactCorruption("known coordinator run registration is unavailable") from exc
