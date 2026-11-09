"""Required local experiment and replay endpoints."""

from typing import Annotated, cast

from fastapi import FastAPI, Query, Request, Response

from app.api.context import ApiContext, Json
from app.api.models import CompareRequest, ForecastRequest, MaterializeRequest, PlanRequest
from app.api.readers import chunk_window, manifest_with_catalog, raw_file
from app.api.service import JobService


def attach_routes(app: FastAPI, context: ApiContext) -> None:
    @app.get("/api/catalog")
    async def catalog() -> Json:
        return context.catalog()

    @app.post("/api/scenarios/materialize")
    async def materialize(body: MaterializeRequest, request: Request) -> Json:
        return await cast(JobService, request.app.state.jobs).submit("materialize", body)

    @app.post("/api/forecast")
    async def forecast(body: ForecastRequest, request: Request) -> Json:
        return await cast(JobService, request.app.state.jobs).submit("forecast", body)

    @app.post("/api/plans")
    async def plans(body: PlanRequest, request: Request) -> Json:
        return await cast(JobService, request.app.state.jobs).submit("plans", body)

    @app.post("/api/compare")
    async def compare(body: CompareRequest, request: Request) -> Json:
        return await cast(JobService, request.app.state.jobs).submit("compare", body)

    attach_read_routes(app, context)


def attach_read_routes(app: FastAPI, context: ApiContext) -> None:

    @app.get("/api/runs/{run_id}/manifest")
    async def manifest(run_id: str) -> Json:
        return manifest_with_catalog(context.store, run_id)

    @app.get("/api/runs/{run_id}/chunks")
    async def chunks(
        run_id: str,
        from_s: Annotated[float, Query(ge=0, allow_inf_nan=False)] = 0,
        limit: Annotated[int, Query(ge=1, le=3)] = 1,
    ) -> Json:
        return chunk_window(context.store, run_id, from_s, limit)

    @app.get("/api/runs/{run_id}/files/{artifact_id}")
    async def replay_file(run_id: str, artifact_id: str) -> Response:
        return Response(
            raw_file(context.store, run_id, artifact_id),
            media_type="application/json",
            headers={"ETag": f'"{artifact_id}"'},
        )
