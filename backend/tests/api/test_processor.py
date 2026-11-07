"""Actual spawn executes real forecast code; cancelled waiters cannot admit a second task."""

from __future__ import annotations

import asyncio
import os
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from app.api.context import ApiContext, Job
from app.api.models import MaterializeRequest
from app.api.planning_jobs import _scaled_visits
from app.api.processor import ProcessProcessor
from app.api.service import BusyError, JobService
from app.data.catalog import SKU_IDS
from app.data.history import TEST_DAY
from app.storage.artifacts import ArtifactStore


def _constant_history() -> bytes:
    rows = ["date,sku_id,visits"]
    for offset in range(56):
        day = TEST_DAY - timedelta(days=56 - offset)
        rows.extend(f"{day.isoformat()},{sku},2" for sku in SKU_IDS)
    return ("\n".join(rows) + "\n").encode()


def test_real_spawn_worker_forecasts_and_stores_semantic_identity(
    tmp_path: Path, contracts_dir: Path
) -> None:
    store = ArtifactStore(tmp_path)
    context = ApiContext.create(store, contracts_dir)
    history_id = store.put_bytes("histories", _constant_history())

    async def execute() -> None:
        processor = ProcessProcessor()
        try:
            result = await processor.execute(
                context.job("forecast", {"history_id": history_id, "model": "mean28"})
            )
            assert processor.last_worker_pid != os.getpid()
            assert processor.last_worker_pid is not None
            semantic = store.read_json("forecasts", result["forecast_id"])
            assert result["forecast_id"] == result["forecast"]["semantic_id"]
            assert "cpu_time_s" not in semantic
            assert set(semantic["predictions"]["visits_by_sku"].values()) == {2.0}
            assert semantic["validation"]["wape"] == 0
        finally:
            await processor.close()

    asyncio.run(execute())


def test_forecast_daily_visits_are_scaled_to_declared_horizon() -> None:
    forecast = {
        "protocol": "qoima-forecast-temporal-1",
        "full_day_s": 28800,
        "training_visits_by_sku": {"SKU": 16.0},
        "predictions": {"visits_by_sku": {"SKU": 24.0}},
    }
    # 3600 /28800=1/8 of a full forecast day; neither input map is already per hour.
    assert _scaled_visits(forecast, 3600) == ({"SKU": 2.0}, {"SKU": 3.0})


class BlockingProcessor:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.calls = 0

    async def execute(self, job: Job) -> dict[str, Any]:
        self.calls += 1
        self.started.set()
        await self.release.wait()
        return {"status": "passed"}


def test_cancelled_client_keeps_worker_busy_until_completion(
    tmp_path: Path, contracts_dir: Path
) -> None:
    context = ApiContext.create(ArtifactStore(tmp_path), contracts_dir)

    async def exercise() -> None:
        processor = BlockingProcessor()
        jobs = JobService(context, processor)
        request = MaterializeRequest(
            layout_version=context.bundle.layout.layout_version,
            profile="large-normal",
            horizon_s=60,
        )
        waiter = asyncio.create_task(jobs.submit("materialize", request))
        await processor.started.wait()
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        with pytest.raises(BusyError):
            await jobs.submit("materialize", request)
        processor.release.set()
        await jobs.finish()
        assert await jobs.submit("materialize", request) == {"status": "passed"}
        assert processor.calls == 1

    asyncio.run(exercise())
