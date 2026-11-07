"""A single owned spawn worker; expensive work never runs in the ASGI event loop."""

from __future__ import annotations

import asyncio
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from typing import Protocol

from app.api.context import Job, Json


class Processor(Protocol):
    async def execute(self, job: Job) -> Json: ...


class ProcessProcessor:
    def __init__(self) -> None:
        self.pool = ProcessPoolExecutor(
            max_workers=1, mp_context=multiprocessing.get_context("spawn")
        )
        self.last_worker_pid: int | None = None

    async def execute(self, job: Job) -> Json:
        from app.api.worker import execute_job

        result = await asyncio.get_running_loop().run_in_executor(self.pool, execute_job, job)
        self.last_worker_pid = result.worker_pid
        return result.payload

    async def close(self) -> None:
        await asyncio.to_thread(self.pool.shutdown, wait=True, cancel_futures=True)
