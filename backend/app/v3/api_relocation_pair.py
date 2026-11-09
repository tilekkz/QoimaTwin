"""Saved N1 pair reads share admission ownership and stream captured arm bytes."""

import asyncio
from base64 import b64encode
from collections.abc import Iterator
from typing import Annotated, cast

from fastapi import FastAPI, Query, Request, Response
from fastapi.responses import StreamingResponse

from app.api.context import ApiContext, Json
from app.api.models import ArtifactId
from app.api.service import JobService
from app.storage.canonical_json import canonical_bytes
from app.v3.api_relocation_pair_worker import preflight

Tick = Annotated[str, Query(pattern=r"^(0|[1-9][0-9]*)$", max_length=20)]
BASE = "/api/v3/relocation-pairs/{pair_id}"


def attach_relocation_pair_routes(app: FastAPI, context: ApiContext) -> None:
    @app.get(BASE + "/result")
    async def result(pair_id: ArtifactId, request: Request) -> Json:
        return await _read(context, request, pair_id, None, "result")

    @app.get(BASE + "/arms/{arm}/manifest")
    async def manifest(pair_id: ArtifactId, arm: str, request: Request) -> Json:
        return await _read(context, request, pair_id, arm, "manifest")

    @app.get(BASE + "/arms/{arm}/files/{artifact_id}")
    async def file(
        pair_id: ArtifactId, arm: str, artifact_id: ArtifactId, request: Request
    ) -> Response:
        value = await _read(context, request, pair_id, arm, "file", artifact_id=artifact_id)
        headers = {
            "ETag": f'"{artifact_id}"',
            **{
                "X-Qoima-" + key.replace("_", "-"): str(value[key])
                for key in (
                    "pair_id",
                    "arm",
                    "native_run_id",
                    "input_hash",
                    "pair_input_hash",
                    "common_input_hash",
                    "registry_common_hash",
                )
            },
        }
        return Response(value["body"], media_type="application/json", headers=headers)

    @app.get(BASE + "/arms/{arm}/bundle")
    async def bundle(pair_id: ArtifactId, arm: str, request: Request) -> StreamingResponse:
        value = await _read(context, request, pair_id, arm, "bundle")
        return StreamingResponse(_records(value), media_type="application/x-ndjson")

    @app.get(BASE + "/arms/{arm}/replay")
    async def replay(pair_id: ArtifactId, arm: str, tick: Tick, request: Request) -> Json:
        return await _read(context, request, pair_id, arm, "replay", tick=int(tick))


async def _read(
    context: ApiContext,
    request: Request,
    identifier: str,
    arm: str | None,
    action: str,
    *,
    artifact_id: str | None = None,
    tick: int | None = None,
) -> Json:
    payload = {
        "pair_id": identifier,
        "arm": arm,
        "action": action,
        "artifact_id": artifact_id,
        "tick": tick,
    }
    await asyncio.to_thread(preflight, context.store, payload)
    job = context.job("relocation-pair-read-v3", payload)
    return await cast(JobService, request.app.state.jobs).read_job(job)


def _records(value: Json) -> Iterator[bytes]:
    yield canonical_bytes(value["header"]) + b"\n"
    for row, raw in value["members"]:
        yield (
            canonical_bytes(
                {"record_type": "file", **row, "body_base64": b64encode(raw).decode("ascii")}
            )
            + b"\n"
        )
