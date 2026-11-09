"""Registered actual common profiles and forecast-bound normal pair execution."""

import asyncio
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI, Request, Response

from app.api.context import ApiContext
from app.api.models import ArtifactId
from app.api.service import JobService
from app.v3.api_forecast_relocation_inputs import (
    ForecastRelocationRequest,
    freeze_request,
    public_id,
)
from app.v3.api_forecast_relocation_storage import known, verified_response
from app.v3.settings import default_inputs


def attach_forecast_relocation_routes(
    app: FastAPI, context: ApiContext, source: Path | None
) -> None:
    source_root = str(source or default_inputs())

    @app.get("/api/v3/forecast-relocation-profiles")
    async def profiles(request: Request) -> dict[str, Any]:
        job = context.job("forecast-relocation-profile-v3", {"source_root": source_root})
        return await cast(JobService, request.app.state.jobs).read_job(job)

    @app.post("/api/v3/forecast-relocation-runs")
    async def submit(body: ForecastRelocationRequest, request: Request) -> dict[str, Any]:
        identifier = await asyncio.to_thread(freeze_request, context.store, body)
        key = public_id(identifier)
        job = context.job(
            "forecast-relocation-v3", {"request_id": identifier, "source_root": source_root}
        )
        read = context.job(
            "forecast-relocation-read-v3",
            {"run_id": key, "artifact_id": None, "source_root": source_root},
        )
        result = await cast(JobService, request.app.state.jobs).submit_job(
            job, key, cached_read=read
        )
        return await asyncio.to_thread(verified_response, context.store, result, key)

    @app.get("/api/v3/forecast-relocation-runs/{run_id}/result")
    async def result(run_id: ArtifactId, request: Request) -> dict[str, Any]:
        return await _read(context, request, source_root, run_id, None)

    @app.get("/api/v3/forecast-relocation-runs/{run_id}/files/{artifact_id}")
    async def file(run_id: ArtifactId, artifact_id: ArtifactId, request: Request) -> Response:
        value = await _read(context, request, source_root, run_id, artifact_id)
        return Response(
            value["body"], media_type=value["media_type"], headers={"ETag": f'"{artifact_id}"'}
        )


async def _read(
    context: ApiContext, request: Request, source: str, identifier: str, artifact_id: str | None
) -> dict[str, Any]:
    await asyncio.to_thread(known, context.store, identifier)
    job = context.job(
        "forecast-relocation-read-v3",
        {"run_id": identifier, "artifact_id": artifact_id, "source_root": source},
    )
    return await cast(JobService, request.app.state.jobs).read_job(job)
