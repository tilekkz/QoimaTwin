"""Worker dispatch, partial status and sanitized failures reuse real publication components."""

from pathlib import Path

import pytest

from app.api.context import Job
from app.api.errors import UnexpectedExecutionError
from app.api.worker import execute_job
from app.storage.artifacts import ArtifactStore
from app.v3 import api_light_worker
from app.v3.api_light_identity import verified_response
from app.v3.api_light_inputs import freeze_profile
from app.v3.flow_run import build_flow_run
from app.v3.flow_transport import write_flow_run
from app.v3.settings import default_inputs
from tests.v3.test_flow_run_fixtures import sample


def test_existing_worker_dispatches_light_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        api_light_worker, "light_job", lambda job: {"status": "partial", "kind": job.kind}
    )
    result = execute_job(Job("light-v3", {}, "unused", "", "", ""))
    assert result.payload == {"status": "partial", "kind": "light-v3"}


def test_actual_partial_artifact_remains_partial_at_publication(tmp_path: Path) -> None:
    inputs, outcome = sample(True)
    run = build_flow_run(inputs, outcome)
    write_flow_run(run, tmp_path / "run", inputs=inputs.frozen_bytes)
    result = api_light_worker.publish_output(
        ArtifactStore(tmp_path / "store"),
        "b" * 64,
        tmp_path / "run",
        {"input_hash": inputs.input_hash},
    )
    assert result["status"] == "partial" and result["operational_admission"] is False
    assert run["metrics"]["at_end"]["completed_units"] == 0
    run["status"] = "complete"
    with pytest.raises(ValueError, match="status"):
        verified_response(run, {"run_id": result["run_id"]})


def test_failed_pipeline_retains_frozen_evidence_and_no_success_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ArtifactStore(tmp_path)
    frozen = freeze_profile(store, default_inputs())
    job = Job("light-v3", {"light_bundle_id": frozen.bundle_id}, str(tmp_path), "", "", "")

    def fail(source: Path, profile: Path, output: Path) -> None:
        assert (source / "provenance.json").exists() and profile.exists()
        output.mkdir()
        (output / "inputs.json").write_bytes(
            store.read_bytes("run_files", frozen.metadata["input_hash"])
        )
        raise RuntimeError("private path and sensitive message")

    monkeypatch.setattr(api_light_worker, "simulate_light_file", fail)
    with pytest.raises(UnexpectedExecutionError) as error:
        api_light_worker.light_job(job)
    assert "private" not in str(error.value)
    assert list((tmp_path / "light-v3-evidence").glob("*/output/inputs.json"))
    assert list((tmp_path / "light-v3-evidence").glob("*/failure.json"))
    assert not (tmp_path / "runs").exists() and not (tmp_path / "requests").exists()
