"""Storage observations use the same immutable native evidence as registered reads."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.storage.canonical_json import sha256_hex
from app.v3 import api_coordinator_registry
from app.v3.coordinator_engine import CoordinatorEngine
from tests.v3.test_api_coordinator_fixtures import CoordinatorApi
from tests.v3.test_api_coordinator_fixtures import registered_hand_api as coordinator_api

__all__ = ["coordinator_api"]


def test_fullness_reads_bound_horizon_and_end_without_running_an_engine(
    coordinator_api: CoordinatorApi, monkeypatch: pytest.MonkeyPatch
) -> None:
    api = coordinator_api

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("A storage observation must not execute an engine")

    monkeypatch.setattr(CoordinatorEngine, "__init__", forbidden)
    monkeypatch.setattr(CoordinatorEngine, "run", forbidden)
    before = len(api.processor.calls)
    first = api.client.get(api.base + "/storage-fullness")
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["run_id"] == api.response["run_id"]
    assert body["native_run_id"] == api.response["native_run_id"]
    assert body["input_hash"] == api.response["input_hash"]
    report = body["report"]
    assert report["source_run_id"] == body["native_run_id"]
    assert report["input_hash"] == body["input_hash"]
    assert report["report_id"] == sha256_hex(
        {key: value for key, value in report.items() if key != "report_id"}
    )
    # This fixture has an analytical graph without authoritative source slot capacities.
    assert report["at_horizon"]["available"] is False
    assert report["at_end"]["available"] is False
    assert api.client.get(api.base + "/storage-fullness").content == first.content
    assert len(api.processor.calls) == before


def test_unknown_fullness_does_not_initialize_registration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*_args: object) -> None:
        pytest.fail("Unknown run lookup must precede registration")

    monkeypatch.setattr(api_coordinator_registry, "freeze_profile", forbidden)
    with TestClient(create_app(tmp_path), raise_server_exceptions=False) as client:
        response = client.get("/api/v3/coordinator-runs/" + "0" * 64 + "/storage-fullness")
    assert response.status_code == 404


@pytest.mark.parametrize("artifact", ["inputs.json", "events/"])
def test_warm_fullness_rechecks_original_bytes_before_projection(
    coordinator_api: CoordinatorApi, artifact: str
) -> None:
    api = coordinator_api
    first = api.client.get(api.base + "/storage-fullness")
    assert first.status_code == 200, first.text
    index = api.store.read_reference("runs", api.response["run_id"])
    row = next(row for row in index["files"] if row["path"].startswith(artifact))
    path = api.store.path("run_files", row["sha256"])
    original = path.read_bytes()
    try:
        path.write_bytes(original + b" ")
        response = api.client.get(api.base + "/storage-fullness")
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "artifact_corruption"
    finally:
        path.write_bytes(original)
    assert api.client.get(api.base + "/storage-fullness").content == first.content


def test_known_fullness_requires_available_registration(
    coordinator_api: CoordinatorApi, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unavailable(*_args: object) -> None:
        raise FileNotFoundError("registered source unavailable")

    monkeypatch.setattr(api_coordinator_registry, "freeze_profile", unavailable)
    api = coordinator_api
    with TestClient(
        create_app(api.store.root, processor=api.processor), raise_server_exceptions=False
    ) as client:
        response = client.get(api.base + "/storage-fullness")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "artifact_corruption"
