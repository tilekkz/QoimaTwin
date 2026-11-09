"""Failed owned jobs keep sanitized evidence and never publish a successful reference."""

from pathlib import Path

import pytest

from app.api.context import Job
from app.errors import InvalidInputError
from app.storage.artifacts import ArtifactCorruption, ArtifactStore
from app.storage.canonical_json import parse_json
from app.v3 import api_whole_worker
from app.v3.api_whole_binding import registration
from app.v3.api_whole_inputs import _versions


def test_invalid_registration_fails_before_engine_and_keeps_sanitized_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invalid(*args: object) -> object:
        raise ValueError("private provider/path text must never leave the worker")

    def forbidden(*args: object) -> object:
        pytest.fail("invalid registration reached the engine")

    monkeypatch.setattr(api_whole_worker, "load_registered", invalid)
    monkeypatch.setattr(api_whole_worker, "simulate_whole_file", forbidden)
    job = Job("whole-v3", {"whole_bundle_id": "a" * 64}, str(tmp_path), "", "", "")
    with pytest.raises(InvalidInputError, match="registered whole validation failed"):
        api_whole_worker.whole_job(job)
    files = list((tmp_path / "whole-v3-evidence").glob("attempt-*/failure.json"))
    assert len(files) == 1
    assert parse_json(files[0].read_bytes()) == {
        "domain": "qoima-v3-whole-api-1",
        "status": "failed",
        "exception_type": "ValueError",
    }
    assert not (tmp_path / "runs").exists()
    assert not (tmp_path / "requests").exists()


def test_missing_registered_dependency_is_artifact_corruption(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    snapshot = {
        **_versions(),
        **{
            key: "a" * 64
            for key in (
                "profile_sha256",
                "request_sha256",
                "frozen_inputs",
                "input_hash",
                "physical_input_hash",
            )
        },
        "files": [],
        "conveyor_files": [],
    }
    identifier = store.put_json("bundles", snapshot)
    with pytest.raises(ArtifactCorruption, match="unavailable"):
        registration(store, identifier)
