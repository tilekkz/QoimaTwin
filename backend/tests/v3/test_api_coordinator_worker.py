"""Failures leave inspectable attempt evidence and never publish a reusable result."""

from pathlib import Path
from typing import Any

import pytest

from app.api.context import Job
from app.api.errors import UnexpectedExecutionError
from app.storage.artifacts import ArtifactStore
from app.storage.canonical_json import parse_json
from app.v3 import api_coordinator_worker as worker
from app.v3.api_coordinator_inputs import FrozenCoordinatorProfile


def test_failed_worker_keeps_attempt_and_can_be_retried_without_success_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frozen = FrozenCoordinatorProfile("b" * 64, {})
    calls: list[str] = []

    def failed(*args: Any, **kwargs: Any) -> Any:
        calls.append("attempt")
        raise RuntimeError("injected execution failure")

    monkeypatch.setattr(worker, "load_registered", lambda *args: frozen)
    monkeypatch.setattr(worker, "restore_inputs", lambda *args: (tmp_path / "profile.json", {}))
    monkeypatch.setattr(worker, "_preflight", lambda *args: (None, None))
    monkeypatch.setattr(worker, "simulate_compiled_coordinator", failed)
    job = Job(
        "coordinator-v3",
        {"coordinator_bundle_id": frozen.bundle_id},
        str(tmp_path / "store"),
        "a" * 64,
        "c" * 64,
        str(tmp_path),
    )
    for _ in range(2):
        with pytest.raises(UnexpectedExecutionError):
            worker.coordinator_job(job)
    assert calls == ["attempt", "attempt"]
    store = ArtifactStore(Path(job.store_root))
    failures = list((store.root / "coordinator-v3-evidence").glob("attempt-*/failure.json"))
    assert len(failures) == 2
    assert all(parse_json(path.read_bytes())["status"] == "failed" for path in failures)
    assert not (store.root / "runs").exists() and not (store.root / "requests").exists()
