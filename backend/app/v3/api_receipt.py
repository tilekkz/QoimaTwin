"""Local registered connected receipt-to-unit endpoints use the shared owned calculation worker."""

import asyncio
from pathlib import Path
from typing import Annotated, cast

from fastapi import FastAPI, Query, Request, Response

from app.api.context import ApiContext, Json
from app.api.models import ArtifactId
from app.api.service import JobService
from app.errors import InvalidInputError
from app.v3 import api_receipt_readers as readers
from app.v3.api_receipt_inputs import ReceiptRequest
from app.v3.api_receipt_registry import ReceiptRegistry
from app.v3.settings import default_inputs

Tick = Annotated[str, Query(pattern=r"^(0|[1-9][0-9]*)$", max_length=20)]


def attach_receipt_routes(app: FastAPI, context: ApiContext, source: Path | None) -> None:
    registry = ReceiptRegistry(context.store, source or default_inputs())

    @app.get("/api/v3/receipt-profiles")
    async def profiles() -> Json:
        return {"profiles": [(await registry.get()).metadata]}

    @app.post("/api/v3/receipt-runs")
    async def submit(body: ReceiptRequest, request: Request) -> Json:
        frozen = await registry.get()
        if any(
            getattr(body, k) != frozen.metadata[k] for k in ("layout_version", "source_revision")
        ):
            raise InvalidInputError("connected registered profile source/layout mismatch")
        job = context.job("receipt-v3", {"receipt_bundle_id": frozen.bundle_id})
        result = await cast(JobService, request.app.state.jobs).submit_job(job, frozen.key())
        return await asyncio.to_thread(readers.verify_result, context.store, result, frozen)

    attach_reads(app, context, registry)


def attach_reads(app: FastAPI, context: ApiContext, registry: ReceiptRegistry) -> None:
    @app.get("/api/v3/receipt-runs/{run_id}")
    async def get_status(run_id: ArtifactId) -> Json:
        return await asyncio.to_thread(readers.status, context.store, run_id, await registry.get())

    @app.get("/api/v3/receipt-runs/{run_id}/manifest")
    async def get_manifest(run_id: ArtifactId) -> Json:
        return await asyncio.to_thread(
            readers.manifest, context.store, run_id, await registry.get()
        )

    @app.get("/api/v3/receipt-runs/{run_id}/files/{artifact_id}")
    async def get_file(run_id: ArtifactId, artifact_id: ArtifactId) -> Response:
        index, _ = await asyncio.to_thread(
            readers.verified_artifact, context.store, run_id, await registry.get()
        )
        raw = await asyncio.to_thread(readers.file_bytes, context.store, index, artifact_id)
        return Response(raw, media_type="application/json", headers={"ETag": f'"{artifact_id}"'})

    @app.get("/api/v3/receipt-runs/{run_id}/checkpoint")
    async def get_checkpoint(run_id: ArtifactId, tick: Tick) -> Json:
        return await asyncio.to_thread(
            readers.checkpoint, context.store, run_id, int(tick), await registry.get()
        )

    @app.get("/api/v3/receipt-runs/{run_id}/events")
    async def get_events(run_id: ArtifactId, start_tick: Tick, end_tick: Tick) -> Json:
        return await asyncio.to_thread(
            readers.events,
            context.store,
            run_id,
            int(start_tick),
            int(end_tick),
            await registry.get(),
        )
