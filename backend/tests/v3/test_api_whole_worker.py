"""Whole dispatch and publication use one worker and keep nested native files separate."""

from pathlib import Path

import pytest

from app.api.context import Job
from app.api.worker import execute_job
from app.v3 import api_whole_worker


def test_shared_worker_dispatches_whole_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        api_whole_worker, "whole_job", lambda job: {"status": "partial", "kind": job.kind}
    )
    result = execute_job(Job("whole-v3", {}, "unused", "", "", ""))
    assert result.payload == {"status": "partial", "kind": "whole-v3"}


def test_native_file_index_ignores_outer_evidence(tmp_path: Path) -> None:
    out = tmp_path / "output"
    (out / "run").mkdir(parents=True)
    (out / "run/manifest.json").write_bytes(b"native")
    (out / "request.json").write_bytes(b"request")
    from app.storage.artifacts import ArtifactStore

    rows = api_whole_worker.index_files(ArtifactStore(tmp_path / "store"), out / "run")
    assert [row["path"] for row in rows] == ["manifest.json"]
