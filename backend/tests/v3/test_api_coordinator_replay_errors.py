"""Existing422/404/500 policy also applies to uncaptured settled reads."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.errors import InvalidInputError
from app.v3 import api_coordinator_registry
from tests.v3.test_api_coordinator_fixtures import CoordinatorApi
from tests.v3.test_api_coordinator_fixtures import registered_hand_api as coordinator_api

__all__ = ["coordinator_api"]


@pytest.mark.parametrize("tick", ["-1", "true", "1.0", "01", " 1", "158000001", "9" * 21])
def test_query_requires_exact_observed_nonnegative_integer(
    coordinator_api: CoordinatorApi,
    tick: str,
) -> None:
    api = coordinator_api
    response = api.client.get(api.base + "/replay", params={"tick": tick})
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "invalid_input"


def test_unknown_replay_does_not_initialize_broken_registration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[bool] = []

    def unavailable(*_args: object) -> None:
        calls.append(True)
        raise InvalidInputError("server-owned source unavailable")

    monkeypatch.setattr(api_coordinator_registry, "freeze_profile", unavailable)
    with TestClient(create_app(tmp_path), raise_server_exceptions=False) as client:
        response = client.get("/api/v3/coordinator-runs/" + "0" * 64 + "/replay?tick=0")
    assert response.status_code == 404
    assert calls == []


def test_known_replay_with_unavailable_registration_is_corruption(
    coordinator_api: CoordinatorApi,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(*_args: object) -> None:
        raise FileNotFoundError("server-owned source unavailable")

    monkeypatch.setattr(api_coordinator_registry, "freeze_profile", unavailable)
    api = coordinator_api
    with TestClient(
        create_app(api.store.root, processor=api.processor), raise_server_exceptions=False
    ) as client:
        response = client.get(api.base + "/replay?tick=102000000")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "artifact_corruption"


@pytest.mark.parametrize("artifact", ["inputs.json", "events/"])
def test_warm_replay_rehashes_inputs_and_events_before_reusing_native_authority(
    coordinator_api: CoordinatorApi,
    artifact: str,
) -> None:
    api = coordinator_api
    assert api.client.get(api.base + "/replay?tick=102000000").status_code == 200
    index = api.store.read_reference("runs", api.response["run_id"])
    row = next(r for r in index["files"] if r["path"].startswith(artifact))
    path = api.store.path("run_files", row["sha256"])
    original = path.read_bytes()
    try:
        path.write_bytes(original + b" ")
        response = api.client.get(api.base + "/replay?tick=104000000")
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "artifact_corruption"
    finally:
        path.write_bytes(original)
