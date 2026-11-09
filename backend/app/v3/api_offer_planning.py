"""Explicit V3 offer planning uses the existing shared calculation admission slot."""

import asyncio
from typing import Any, cast

from fastapi import FastAPI, Request, Response

from app.api.context import ApiContext
from app.api.models import ArtifactId
from app.api.service import JobService
from app.v3.api_offer_planning_inputs import OfferPlanningRequest, freeze_request, public_id
from app.v3.api_offer_planning_storage import known, verified_response


def attach_offer_planning_routes(app: FastAPI, context: ApiContext) -> None:
    @app.post("/api/v3/offer-plans")
    async def submit(body: OfferPlanningRequest, request: Request) -> dict[str, Any]:
        identifier = await asyncio.to_thread(freeze_request, context.store, body)
        key = public_id(identifier)
        job = context.job("offer-planning-v3", {"request_id": identifier})
        read = context.job("offer-planning-read-v3", {"planning_id": key, "artifact_id": None})
        result = await cast(JobService, request.app.state.jobs).submit_job(
            job, key, cached_read=read
        )
        return await asyncio.to_thread(verified_response, context.store, result, key)

    @app.get("/api/v3/offer-plans/{planning_id}/result")
    async def result(planning_id: ArtifactId, request: Request) -> dict[str, Any]:
        return await _read(context, request, planning_id, None)

    @app.get("/api/v3/offer-plans/{planning_id}/files/{artifact_id}")
    async def file(planning_id: ArtifactId, artifact_id: ArtifactId, request: Request) -> Response:
        value = await _read(context, request, planning_id, artifact_id)
        return Response(
            value["body"], media_type=value["media_type"], headers={"ETag": f'"{artifact_id}"'}
        )


async def _read(
    context: ApiContext, request: Request, identifier: str, artifact_id: str | None
) -> dict[str, Any]:
    await asyncio.to_thread(known, context.store, identifier)
    job = context.job(
        "offer-planning-read-v3", {"planning_id": identifier, "artifact_id": artifact_id}
    )
    return await cast(JobService, request.app.state.jobs).read_job(job)
