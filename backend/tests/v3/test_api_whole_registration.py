"""Registered whole choices use the same owned calculation slot, never request paths."""

import asyncio
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.api.context import ApiContext
from app.api.service import BusyError, JobService
from app.storage.artifacts import ArtifactStore
from app.v3.api_whole_inputs import PROFILE, WholeRequest
from tests.v3.test_api_manual import HoldingProcessor


def test_registration_import_is_independent_of_api_bootstrap() -> None:
    result = subprocess.run(
        [sys.executable, "-c", "from app.v3.api_whole_inputs import WholeRequest"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "change",
    [
        {"profile": "unknown"},
        {"profile_path": "private"},
        {"horizon_tick": 1},
        {"quantity_units": True},
        {"source_revision": 1},
    ],
)
def test_requests_only_select_registered_identity(change: dict[str, Any]) -> None:
    value = {"profile": PROFILE, "layout_version": "v3", "source_revision": "pinned"}
    with pytest.raises(ValidationError):
        WholeRequest.from_data({**value, **change})


def test_whole_job_retains_shared_slot_after_client_cancellation(tmp_path: Path) -> None:
    async def exercise() -> None:
        context = ApiContext.create(ArtifactStore(tmp_path), Path("../contracts"))
        processor = HoldingProcessor()
        jobs = JobService(context, processor)
        task = asyncio.create_task(jobs.submit_job(context.job("whole-v3", {}), "a" * 64))
        await processor.started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        for kind in ("receipt-v3", "light-v3", "manual-v3", "materialize"):
            with pytest.raises(BusyError):
                await jobs.submit_job(context.job(kind, {}), "b" * 64)
        processor.release.set()
        await jobs.finish()
        assert len(processor.calls) == 1

    asyncio.run(exercise())
