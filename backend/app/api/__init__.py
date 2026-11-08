"""Local FastAPI application; launch with python -m app.api (ADR0018)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.api.context import ApiContext
from app.api.errors import attach_error_handlers
from app.api.explanations import ExplanationService, attach_explanation_route
from app.api.processor import Processor, ProcessProcessor
from app.api.routes import attach_routes
from app.api.service import JobService
from app.explanations import MercurySettings
from app.settings import default_contracts_dir, repository_root
from app.storage.artifacts import ArtifactStore
from app.v3.api_manual import attach_manual_routes
from app.v3.registration import attach_v3_routes


def create_app(
    store_root: Path | None = None,
    *,
    processor: Processor | None = None,
    contracts_dir: Path | None = None,
    explanation_settings: MercurySettings | None = None,
    v3_inputs: Path | None = None,
) -> FastAPI:
    store = ArtifactStore(store_root or repository_root() / "backend" / "artifacts" / "api")
    context = ApiContext.create(store, contracts_dir or default_contracts_dir())
    explanations = ExplanationService(store, explanation_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        owned = ProcessProcessor() if processor is None else None
        actual = owned if owned is not None else processor
        if actual is None:
            raise RuntimeError("API processor initialization failed")
        jobs = JobService(context, actual)
        app.state.jobs = jobs
        try:
            yield
        finally:
            await jobs.finish()
            await explanations.finish()
            if owned is not None:
                await owned.close()

    app = FastAPI(title="QoimaTwin local experiment API", version="1", lifespan=lifespan)
    attach_error_handlers(app)
    attach_routes(app, context)
    attach_explanation_route(app, explanations)
    attach_v3_routes(app, v3_inputs)
    attach_manual_routes(app, context, v3_inputs)
    _attach_flow_routes(app, context, v3_inputs)
    return app


def _attach_flow_routes(app: FastAPI, context: ApiContext, source: Path | None) -> None:
    from app.v3.api_coordinator import attach_coordinator_routes
    from app.v3.api_light import attach_light_routes
    from app.v3.api_receipt import attach_receipt_routes
    from app.v3.api_whole import attach_whole_routes

    attach_light_routes(app, context, source)
    attach_receipt_routes(app, context, source)
    attach_whole_routes(app, context, source)
    attach_coordinator_routes(app, context, source)
