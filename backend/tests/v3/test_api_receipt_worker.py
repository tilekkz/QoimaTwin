"""A real receipt publication retains partial status and failed attempts retain evidence."""

from pathlib import Path

import pytest

from app.api.context import Job
from app.api.errors import UnexpectedExecutionError
from app.api.worker import execute_job
from app.storage.artifacts import ArtifactStore
from app.v3 import api_receipt_worker
from app.v3.api_receipt_identity import verified_response
from app.v3.api_receipt_inputs import freeze_profile
from app.v3.receipt_run import build_receipt_run
from app.v3.receipt_transport import write_receipt_run
from app.v3.settings import default_inputs
from tests.v3.test_receipt_run_fixtures import sample


def test_shared_worker_dispatches_receipt_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        api_receipt_worker, "receipt_job", lambda job: {"status": "partial", "kind": job.kind}
    )
    result = execute_job(Job("receipt-v3", {}, "unused", "", "", ""))
    assert result.payload == {"status": "partial", "kind": "receipt-v3"}


def test_partial_receipt_cannot_be_published_as_complete(tmp_path: Path) -> None:
    inputs, outcome = sample(150_000_000, 150_000_000)
    run = build_receipt_run(inputs, outcome)
    write_receipt_run(run, tmp_path / "run", inputs=inputs.frozen_bytes)
    result = api_receipt_worker.publish_output(
        ArtifactStore(tmp_path / "store"),
        "b" * 64,
        tmp_path / "run",
        {"input_hash": inputs.input_hash},
    )
    assert result["status"] == "partial" and result["operational_admission"] is False
    assert run["receipt_metrics"]["at_end"]["credited_units"] == 24
    assert run["metrics"]["at_end"]["completed_units"] == 0
    run["status"] = "complete"
    with pytest.raises(ValueError, match="status"):
        verified_response(run, {"run_id": result["run_id"]})


def test_failed_receipt_retains_inputs_and_has_no_success_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ArtifactStore(tmp_path)
    frozen = freeze_profile(store, default_inputs())
    job = Job("receipt-v3", {"receipt_bundle_id": frozen.bundle_id}, str(tmp_path), "", "", "")

    def fail(source: Path, profile: Path, output: Path) -> None:
        assert (source / "provenance.json").exists() and profile.exists()
        output.mkdir()
        (output / "inputs.json").write_bytes(
            store.read_bytes("run_files", frozen.metadata["input_hash"])
        )
        raise RuntimeError("private path and sensitive message")

    monkeypatch.setattr(api_receipt_worker, "simulate_receipt_file", fail)
    with pytest.raises(UnexpectedExecutionError) as caught:
        api_receipt_worker.receipt_job(job)
    assert "private" not in str(caught.value)
    assert list((tmp_path / "receipt-v3-evidence").glob("*/output/inputs.json"))
    assert list((tmp_path / "receipt-v3-evidence").glob("*/failure.json"))
    assert not (tmp_path / "runs").exists() and not (tmp_path / "requests").exists()
