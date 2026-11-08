"""Real partial receipt state and failed worker attempts remain observable at the API seam."""

import asyncio
from pathlib import Path

import pytest

from app.api.context import ApiContext, Job, Json
from app.api.errors import UnexpectedExecutionError
from app.api.service import BusyError, JobService
from app.v3 import api_receipt_readers as readers
from tests.v3.test_api_receipt_independent_fixtures import registered_hand


def test_partial_cap_retains_actual_receiver_return_and_unpicked_unit_claim(tmp_path: Path) -> None:
    hand = registered_hand(tmp_path)
    identifier = hand.response["run_id"]
    assert readers.verify_result(hand.store, hand.response, hand.frozen)["status"] == "partial"
    state = readers.checkpoint(hand.store, identifier, 28_000_000, hand.frozen)["checkpoint"][
        "state"
    ]
    receipt = state["receipts"][0]
    assert receipt["credited_tick"] == 12_000_000 and receipt["placed_tick"] == 23_000_000
    assert receipt["returned_tick"] is None
    receiver = next(worker for worker in state["workers"] if worker["actor_id"] == "R01")
    assert receiver["operation"]["planned_end_tick"] == 33_000_000
    assert state["inventory"]["claims"] == [
        {
            "claim_id": "pick:O1",
            "job_id": "O1",
            "container_id": "HU2",
            "unit_ids": ["HU2:unit:0001", "HU2:unit:0002", "HU2:unit:0003"],
            "whole_hu": False,
        }
    ]
    assert len(state["stock"]["locations"]) == 48
    units = [row for row in state["stock"]["locations"] if row["unit_id"].startswith("HU2:")]
    assert len(units) == 24 and {row["container_id"] for row in units} == {"HU2"}
    assert hand.response["operational_admission"] is False


class FailingOnceProcessor:
    def __init__(self, response: Json) -> None:
        self.response, self.calls = response, 0
        self.started, self.release = asyncio.Event(), asyncio.Event()

    async def execute(self, job: Job) -> Json:
        assert job.kind == "receipt-v3"
        self.calls += 1
        if self.calls == 1:
            self.started.set()
            await self.release.wait()
            raise UnexpectedExecutionError("controlled receipt attempt failure")
        return self.response


def test_failed_receipt_job_is_uncached_and_retry_waits_for_actual_worker_exit(
    tmp_path: Path,
) -> None:
    hand = registered_hand(tmp_path)

    async def exercise() -> None:
        context = ApiContext.create(hand.store, Path("../contracts"))
        processor = FailingOnceProcessor(hand.response)
        service = JobService(context, processor)
        job = context.job("receipt-v3", {"receipt_bundle_id": hand.frozen.bundle_id})
        key = hand.frozen.key()
        first = asyncio.create_task(service.submit_job(job, key))
        await processor.started.wait()
        assert service.active is not None and not service.active.done()
        with pytest.raises(BusyError):
            await service.submit_job(job, key)
        processor.release.set()
        with pytest.raises(UnexpectedExecutionError):
            await first
        assert service.active.done() and hand.store.read_reference("requests", key) is None
        result = await service.submit_job(job, key)
        assert processor.calls == 2 and result == hand.response
        assert hand.store.read_reference("requests", key) == hand.response
        assert readers.verify_result(hand.store, result, hand.frozen) == hand.response

    asyncio.run(exercise())
