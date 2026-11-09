"""Independent warm-read semantic controls; this hand fixture grants no source approval."""

from pathlib import Path

import pytest

from app.storage.canonical_json import canonical_bytes, parse_json, sha256_hex
from app.v3 import api_coordinator_fullness, api_coordinator_registry
from app.v3.interface import Json
from tests.v3.test_api_coordinator_fixtures import CoordinatorApi
from tests.v3.test_api_coordinator_fixtures import registered_hand_api as coordinator_api

__all__ = ["coordinator_api"]


def _forbidden(*_args: object, **_kwargs: object) -> None:
    pytest.fail("An invalid public binding must fail before storage projection")


def _rewrite_reference(path: Path, index: Json) -> None:
    path.write_bytes(canonical_bytes({"value": index, "content_sha256": sha256_hex(index)}))


def test_rehashed_result_numeric_alias_fails_before_warm_projection(
    coordinator_api: CoordinatorApi, monkeypatch: pytest.MonkeyPatch
) -> None:
    api = coordinator_api
    first = api.client.get(api.base + "/storage-fullness")
    assert first.status_code == 200, first.text
    path = api.store.path("runs", api.response["run_id"])
    original = path.read_bytes()
    index = parse_json(original)["value"]
    row = next(row for row in index["request_files"] if row["path"] == "result.json")
    result = api.store.read_json("run_files", row["sha256"])
    assert result["operational_admission"] is False
    result["operational_admission"] = 0
    raw = canonical_bytes(result)
    row.update(sha256=api.store.put_bytes("run_files", raw), bytes=len(raw))
    try:
        _rewrite_reference(path, index)
        with monkeypatch.context() as patch:
            patch.setattr(api_coordinator_fullness, "_fullness_from_context", _forbidden)
            response = api.client.get(api.base + "/storage-fullness")
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "artifact_corruption"
    finally:
        path.write_bytes(original)
    assert api.client.get(api.base + "/storage-fullness").content == first.content


def test_rehashed_native_id_cannot_replace_warm_public_binding(
    coordinator_api: CoordinatorApi, monkeypatch: pytest.MonkeyPatch
) -> None:
    api = coordinator_api
    first = api.client.get(api.base + "/storage-fullness")
    assert first.status_code == 200, first.text
    path = api.store.path("runs", api.response["run_id"])
    original = path.read_bytes()
    index = parse_json(original)["value"]
    assert index["native_run_id"] != index["run_id"]
    index["native_run_id"] = index["run_id"]
    try:
        _rewrite_reference(path, index)
        with monkeypatch.context() as patch:
            patch.setattr(api_coordinator_fullness, "_fullness_from_context", _forbidden)
            response = api.client.get(api.base + "/storage-fullness")
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "artifact_corruption"
    finally:
        path.write_bytes(original)
    assert api.client.get(api.base + "/storage-fullness").content == first.content


def test_native_id_is_not_an_alias_of_registered_public_id(
    coordinator_api: CoordinatorApi, monkeypatch: pytest.MonkeyPatch
) -> None:
    api = coordinator_api
    assert api.response["native_run_id"] != api.response["run_id"]
    monkeypatch.setattr(api_coordinator_registry.CoordinatorRegistry, "get", _forbidden)
    monkeypatch.setattr(api_coordinator_fullness, "_fullness_from_context", _forbidden)
    url = "/api/v3/coordinator-runs/" + api.response["native_run_id"] + "/storage-fullness"
    response = api.client.get(url)
    assert response.status_code == 404
