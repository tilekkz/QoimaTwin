"""Strict registered input and shared admission proofs for the manual proposal."""

import asyncio
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.api.context import ApiContext, Job
from app.api.models import MaterializeRequest
from app.api.service import BusyError, JobService
from app.storage.artifacts import ArtifactStore
from app.v3.api_manual_inputs import freeze_profile
from app.v3.settings import default_inputs


class HoldingProcessor:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.calls: list[Job] = []

    async def execute(self, job: Job) -> dict[str, Any]:
        self.calls.append(job)
        self.started.set()
        await self.release.wait()
        return {"status": "passed"}


def test_metadata_and_strict_boundary(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path, processor=HoldingProcessor())) as client:
        response = client.get("/api/v3/manual-profiles")
        assert response.status_code == 200
        profile = response.json()["profiles"][0]
        assert profile["profile"] == "manual-whole-hu-demo-v1"
        assert profile["baseline_hus"] == 530 and profile["sku_count"] == 200
        assert profile["actor_ids_preserved"] == 24 and profile["job_count"] == 4
        assert profile["frontend_adapter"] is profile["full_v3_warehouse"] is False
        updates: tuple[dict[str, Any], ...] = (
            {"profile": "../../bad"},
            {"horizon_tick": 1},
            {"events": []},
            {"proposal_path": "secret"},
            {"layout_version": "v2"},
            {"source_revision": "wrong"},
            {"rates": {}},
            {"materialized": {}},
        )
        for update in updates:
            body = {key: profile[key] for key in ("profile", "layout_version", "source_revision")}
            result = client.post("/api/v3/manual-runs", json={**body, **update})
            assert result.status_code == 422
            assert "secret" not in result.text


def test_frozen_inputs_are_domain_bound_and_verified(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    frozen = freeze_profile(store, default_inputs())
    second = freeze_profile(store, default_inputs())
    assert frozen == second
    snapshot = store.read_json("bundles", frozen.bundle_id)
    assert snapshot["domain"] == "qoima-v3-manual-api-1"
    for row in snapshot["files"]:
        store.read_bytes("run_files", row["sha256"])
    assert frozen.metadata["profile_sha256"]


def test_shared_admission_survives_cancellation_and_drains(tmp_path: Path) -> None:
    async def exercise() -> None:
        context = ApiContext.create(ArtifactStore(tmp_path), Path("../contracts"))
        processor = HoldingProcessor()
        service = JobService(context, processor)
        job = context.job("manual-v3", {"test": True})
        waiter = asyncio.create_task(service.submit_job(job, "a" * 64))
        await processor.started.wait()
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        body = MaterializeRequest(
            layout_version="qoima-72x48-v2", profile="large-normal", horizon_s=1
        )
        with pytest.raises(BusyError):
            await service.submit("materialize", body)
        drain = asyncio.create_task(service.finish())
        await asyncio.sleep(0)
        assert not drain.done()
        processor.release.set()
        await drain
        assert await service.submit_job(job, "a" * 64) == {"status": "passed"}
        assert len(processor.calls) == 1

    asyncio.run(exercise())
