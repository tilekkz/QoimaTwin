"""Validated references, immutable request reuse and bounded job admission."""

from __future__ import annotations

import asyncio

from app.api.context import ApiContext, Job, JobKind, Json
from app.api.models import VersionedRequest
from app.api.processor import Processor
from app.errors import AppError, InvalidInputError
from app.storage.artifacts import ArtifactCorruption
from app.storage.canonical_json import canonical_bytes, sha256_hex
from app.version import ENGINE_VERSION

REF_FIELDS = {
    "scenario_id": "scenarios",
    "history_id": "histories",
    "forecast_id": "forecasts",
    "assignment_id": "assignments",
    "plan_id": "plans",
}


class BusyError(AppError):
    code = "calculation_busy"
    http_status = 409


class JobService:
    def __init__(self, context: ApiContext, processor: Processor) -> None:
        self.context = context
        self.processor = processor
        self.active: asyncio.Task[Json] | None = None

    async def submit(self, kind: JobKind, request: VersionedRequest) -> Json:
        payload = request.model_dump(mode="json", exclude_none=True)
        self._validate(payload)
        job = self.context.job(kind, payload)
        key = sha256_hex(
            {
                "protocol": "qoima-api-1",
                "kind": kind,
                "payload": payload,
                "bundle_id": job.bundle_id,
                "assignment_id": job.assignment_id,
                "engine_version": ENGINE_VERSION,
            }
        )
        return await self.submit_job(job, key)

    async def submit_job(self, job: Job, key: str, *, cached_read: Job | None = None) -> Json:
        """Share one admission slot and cancellation/drain policy across API domains."""
        cached = self.context.store.read_reference("requests", key)
        if cached_read is not None and (
            cached is not None or self.context.store.path("requests", key).exists()
        ):
            if type(cached) is not dict:
                raise ArtifactCorruption("cached request result must be an object")
            verified = await self.read_job(cached_read)
            if canonical_bytes(cached) != canonical_bytes(verified):
                raise ArtifactCorruption("cached request differs from fresh authority")
            return verified
        if cached is not None:
            return dict(cached)
        if self.active is not None and not self.active.done():
            raise BusyError("one calculation is already running; retry after it completes")
        self.active = asyncio.create_task(self._execute(job, key))
        # A disconnected client does not cancel the child or release its admission slot.
        return await asyncio.shield(self.active)

    async def read_job(self, job: Job) -> Json:
        """Authenticate freshly in the same owned worker, without publishing a request cache."""
        if self.active is not None and not self.active.done():
            raise BusyError("one calculation is already running; retry after it completes")
        self.active = asyncio.create_task(self.processor.execute(job))
        return await asyncio.shield(self.active)

    def _validate(self, payload: Json) -> None:
        if payload["layout_version"] != self.context.bundle.layout.layout_version:
            raise InvalidInputError(
                "request layout_version differs from the active contract bundle"
            )
        for field, namespace in REF_FIELDS.items():
            if field in payload:
                self.context.store.read_bytes(namespace, payload[field])

    async def _execute(self, job: Job, key: str) -> Json:
        result = await self.processor.execute(job)
        self.context.store.publish_reference("requests", key, result)
        return result

    async def finish(self) -> None:
        if self.active is not None:
            await asyncio.gather(self.active, return_exceptions=True)
