"""Owned read admission, cancellation and preserved failed attempts without real workers."""

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi import FastAPI

from app.api.context import Job
from app.api.service import BusyError, JobService
from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3 import api_offer_planning_worker as worker
from app.v3.offer_planning_cli_models import RAW_NAMES, PlanningFiles
from app.v3.offer_planning_cli_storage import request_record
from tests.v3.test_api_offer_planning import ApiCase, body
from tests.v3.test_api_offer_planning import api_case as api_case


def test_cancelled_read_keeps_slot_finish_drains_and_no_cache(api_case: ApiCase) -> None:
    async def scenario() -> None:
        started, release = asyncio.Event(), asyncio.Event()
        calls: list[Job] = []

        class Blocking:
            async def execute(self, job: Job) -> dict[str, Any]:
                calls.append(job)
                started.set()
                await release.wait()
                return {"status": "no-op"}

        context = cast(FastAPI, api_case.client.app).state.jobs.context
        service = JobService(context, Blocking())
        job = context.job("offer-planning-read-v3", {"planning_id": "a" * 64})
        request = asyncio.create_task(service.read_job(job))
        await started.wait()
        request.cancel()
        with pytest.raises(asyncio.CancelledError):
            await request
        with pytest.raises(BusyError):
            await service.read_job(job)
        with pytest.raises(BusyError):
            await service.submit_job(job, "b" * 64)
        finish = asyncio.create_task(service.finish())
        await asyncio.sleep(0)
        assert not finish.done()
        release.set()
        await finish
        assert len(calls) == 1
        assert not (api_case.store.root / "requests").exists()

    asyncio.run(scenario())


def test_failure_preserves_request_and_partial_files_without_publication(
    api_case: ApiCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failed(paths: PlanningFiles, model: str, out: Path) -> Any:
        out.mkdir()
        (out / "partial.json").write_bytes(b'{"observed":true}')
        raise ValueError("secret path C:/private must not escape")

    monkeypatch.setattr(worker, "plan_offer_files", failed)
    response = api_case.client.post("/api/v3/offer-plans", json=body())
    assert response.status_code == 422
    assert "private" not in response.text
    attempts = list((api_case.store.root / "offer-planning-v3-evidence").iterdir())
    assert len(attempts) == 1
    assert (attempts[0] / "request.json").is_file()
    assert (attempts[0] / "output/partial.json").read_bytes() == b'{"observed":true}'
    assert parse_json((attempts[0] / "failure.json").read_bytes())["status"] == "failed"
    assert not (api_case.store.root / "runs").exists()
    assert not (api_case.store.root / "requests").exists()


def test_independently_valid_other_request_cannot_be_published(
    api_case: ApiCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    producer = cast(
        Callable[[PlanningFiles, str, Path], dict[str, Any]], vars(worker)["plan_offer_files"]
    )

    def other_request(paths: PlanningFiles, model: str, out: Path) -> dict[str, Any]:
        result = producer(paths, model, out)
        (out / "raw/history.csv").write_bytes(b"different-authenticated-history-double\r\n")
        raw = {name: (out / "raw" / name).read_bytes() for name in RAW_NAMES}
        (out / "request.json").write_bytes(canonical_bytes(request_record(model, raw)))
        return result

    monkeypatch.setattr(worker, "plan_offer_files", other_request)
    response = api_case.client.post("/api/v3/offer-plans", json=body())
    assert response.status_code == 500
    assert not (api_case.store.root / "runs").exists()
    assert not (api_case.store.root / "requests").exists()
