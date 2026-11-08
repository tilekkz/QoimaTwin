"""Prewritten HTTP ordering: unknown references precede server registration authority."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.errors import InvalidInputError
from app.v3 import api_coordinator_registry
from tests.v3.test_api_coordinator_fixtures import CoordinatorApi
from tests.v3.test_api_coordinator_fixtures import registered_hand_api as coordinator_api

__all__ = ["coordinator_api"]

READS = (
    "",
    "/manifest",
    "/files/" + "a" * 64,
    "/checkpoint?tick=0",
    "/events?start_tick=0&end_tick=1",
)


@pytest.mark.parametrize("suffix", READS)
def test_unknown_http_run_does_not_load_broken_server_registration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    suffix: str,
) -> None:
    calls: list[bool] = []

    def unavailable(*_args: object) -> None:
        calls.append(True)
        raise InvalidInputError("server-owned source evidence unavailable")

    monkeypatch.setattr(api_coordinator_registry, "freeze_profile", unavailable)
    with TestClient(create_app(tmp_path), raise_server_exceptions=False) as client:
        response = client.get("/api/v3/coordinator-runs/" + "0" * 64 + suffix)
    assert response.status_code == 404, response.text
    assert calls == []


@pytest.mark.parametrize("suffix", READS)
@pytest.mark.parametrize("failure", [InvalidInputError, FileNotFoundError])
def test_known_http_run_has_server_corruption_when_fresh_registration_fails(
    coordinator_api: CoordinatorApi,
    monkeypatch: pytest.MonkeyPatch,
    suffix: str,
    failure: type[Exception],
) -> None:
    def unavailable(*_args: object) -> None:
        raise failure("server-owned source evidence unavailable")

    monkeypatch.setattr(api_coordinator_registry, "freeze_profile", unavailable)
    with TestClient(
        create_app(coordinator_api.store.root, processor=coordinator_api.processor),
        raise_server_exceptions=False,
    ) as client:
        response = client.get(coordinator_api.base + suffix)
    assert response.status_code == 500, response.text
    assert response.json()["error"]["code"] == "artifact_corruption"
