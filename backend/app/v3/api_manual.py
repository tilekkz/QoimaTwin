"""Bounded local whole-HU manual proposal endpoints, sharing V2's owned worker."""

import asyncio
from pathlib import Path
from typing import Annotated, cast

from fastapi import FastAPI, Query, Request, Response

from app.api.context import ApiContext, Json
from app.api.models import ArtifactId
from app.api.service import JobService
from app.errors import InvalidInputError
from app.v3.api_manual_inputs import ManualRequest, freeze_profile
from app.v3.api_manual_readers import file_bytes, manifest, run_index, seek, verify_result
from app.v3.settings import default_inputs


def attach_manual_routes(app: FastAPI, context: ApiContext, source: Path | None) -> None:
    frozen = freeze_profile(context.store, source or default_inputs())

    @app.get("/api/v3/manual-profiles")
    async def profiles() -> Json:
        return {"profiles": [frozen.metadata]}

    @app.post("/api/v3/manual-runs")
    async def submit(body: ManualRequest, request: Request) -> Json:
        if any(
            getattr(body, key) != frozen.metadata[key]
            for key in ("layout_version", "source_revision")
        ):
            raise InvalidInputError("manual profile source/layout binding mismatch")
        job = context.job("manual-v3", {"manual_bundle_id": frozen.bundle_id})
        jobs = cast(JobService, request.app.state.jobs)
        result = await jobs.submit_job(job, frozen.key())
        return await asyncio.to_thread(
            verify_result, context.store, result, expected_bundle_id=frozen.bundle_id
        )

    attach_manual_read_routes(app, context)


def attach_manual_read_routes(app: FastAPI, context: ApiContext) -> None:
    @app.get("/api/v3/manual-runs/{run_id}/manifest")
    async def get_manifest(run_id: ArtifactId) -> Json:
        return await asyncio.to_thread(manifest, context.store, run_id)

    @app.get("/api/v3/manual-runs/{run_id}/files/{artifact_id}")
    async def get_file(run_id: ArtifactId, artifact_id: ArtifactId) -> Response:
        index = await asyncio.to_thread(run_index, context.store, run_id)
        raw = await asyncio.to_thread(file_bytes, context.store, index, artifact_id)
        return Response(raw, media_type="application/json", headers={"ETag": f'"{artifact_id}"'})

    @app.get("/api/v3/manual-runs/{run_id}/seek")
    async def get_seek(
        run_id: ArtifactId,
        cutoff_tick: Annotated[int, Query(ge=0)],
    ) -> Json:
        return await asyncio.to_thread(seek, context.store, run_id, cutoff_tick)
