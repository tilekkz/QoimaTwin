"""Only a registered receipt profile enters the one shared API calculation slot."""

import asyncio
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.api.context import ApiContext
from app.api.service import BusyError, JobService
from app.storage.artifacts import ArtifactStore
from tests.v3.test_api_manual import HoldingProcessor


def test_receipt_registration_import_is_independent_of_api_bootstrap() -> None:
    result = subprocess.run(
        [sys.executable, "-c", "from app.v3.api_receipt_inputs import ReceiptRequest"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_registered_receipt_metadata_and_invalid_choices(tmp_path: Path) -> None:
    processor = HoldingProcessor()
    with TestClient(create_app(tmp_path, processor=processor)) as client:
        response = client.get("/api/v3/receipt-profiles")
        assert response.status_code == 200, response.text
        metadata = response.json()["profiles"][0]
        assert metadata["profile"] == "explicit-received-small-three-units-v1"
        assert metadata["baseline_hus"] == 530 and metadata["baseline_units"] == 12256
        assert metadata["actor_ids_preserved"] == 24 and metadata["receipt_count"] == 1
        assert metadata["receipt_units"] == 24 and metadata["job_count"] == 1
        assert metadata["frontend_adapter"] is False and metadata["full_v3"] is False
        body = {key: metadata[key] for key in ("profile", "layout_version", "source_revision")}
        choices: tuple[dict[str, Any], ...] = (
            {"profile": "unknown"},
            {"profile_path": "private"},
            {"source_revision": "wrong"},
            {"layout_version": "v2"},
            {"horizon_tick": 1},
            {"quantity_units": True},
        )
        for choice in choices:
            rejected = client.post("/api/v3/receipt-runs", json={**body, **choice})
            assert rejected.status_code == 422 and "private" not in rejected.text
        assert processor.calls == []


def test_receipt_job_holds_shared_slot_after_client_cancellation(tmp_path: Path) -> None:
    async def exercise() -> None:
        context = ApiContext.create(ArtifactStore(tmp_path), Path("../contracts"))
        processor = HoldingProcessor()
        jobs = JobService(context, processor)
        task = asyncio.create_task(jobs.submit_job(context.job("receipt-v3", {}), "a" * 64))
        await processor.started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        for kind in ("light-v3", "manual-v3", "materialize"):
            with pytest.raises(BusyError):
                await jobs.submit_job(context.job(kind, {}), "b" * 64)
        processor.release.set()
        await jobs.finish()
        assert len(processor.calls) == 1

    asyncio.run(exercise())
