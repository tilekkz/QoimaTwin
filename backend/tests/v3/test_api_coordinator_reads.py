"""Prewritten exact captured-state, raw evidence and paid-return boundary checks."""

from hashlib import sha256

from app.v3.api_coordinator_readers import verify_result
from tests.v3.test_api_coordinator_fixtures import CoordinatorApi
from tests.v3.test_api_coordinator_fixtures import registered_hand_api as coordinator_api

__all__ = ["coordinator_api"]


def test_partial_paid_return_is_preserved_on_status_and_idempotent_repeat(
    coordinator_api: CoordinatorApi,
) -> None:
    api = coordinator_api
    assert api.response["status"] == "partial"
    assert api.response["resource_drained_tick"] is None
    assert api.response["observation_end_tick"] == 158_000_000
    assert api.response["capabilities"]["arbitrary_seek"] is False
    status = api.client.get(api.base)
    assert status.status_code == 200 and status.json() == api.response
    repeat = api.client.post("/api/v3/coordinator-runs", json=api.body)
    assert repeat.status_code == 200 and repeat.json() == api.response
    assert len(api.processor.calls) == 1
    assert verify_result(api.store, api.response, api.frozen) == api.response


def test_captured_end_preserves_all_carts_and_two_actual_open_returns(
    coordinator_api: CoordinatorApi,
) -> None:
    api = coordinator_api
    response = api.client.get(api.base + "/checkpoint", params={"tick": "158000000"})
    assert response.status_code == 200, response.text
    state = response.json()["checkpoint"]
    workers = {row["actor_id"]: row for row in state["workers"]}
    assert len(workers) == 24 and len(state["carts"]) == 1
    for actor in ("P11", "P12"):
        assert workers[actor]["operation"]["kind"] == "role_return"
        assert workers[actor]["operation"]["planned_end_tick"] == 160_000_000
    assert api.client.get(api.base + "/checkpoint", params={"tick": "158000001"}).status_code == 422


def test_half_open_window_and_unknown_paths_keep_their_declared_boundaries(
    coordinator_api: CoordinatorApi,
) -> None:
    api = coordinator_api
    response = api.client.get(
        api.base + "/events",
        params={
            "start_tick": "154000000",
            "end_tick": "156000000",
        },
    )
    assert response.status_code == 200, response.text
    rows = response.json()["events"]
    assert all(154_000_000 <= row["tick"] < 156_000_000 for row in rows)
    assert any(row["tick"] == 154_000_000 and row["actor_id"] == "P12" for row in rows)
    assert not any(row["tick"] == 156_000_000 for row in rows)
    assert api.client.get(api.base + "/files/" + "0" * 64).status_code == 404
    assert api.client.get("/api/v3/coordinator-runs/" + "0" * 64).status_code == 404


def test_every_authorized_raw_file_preserves_its_published_hash(
    coordinator_api: CoordinatorApi,
) -> None:
    api = coordinator_api
    response = api.client.get(api.base + "/manifest")
    assert response.status_code == 200
    manifest = response.json()
    for row in [*manifest["files"], *manifest["request_files"]]:
        file = api.client.get(api.base + "/files/" + row["sha256"])
        assert file.status_code == 200 and len(file.content) == row["bytes"]
        assert sha256(file.content).hexdigest() == row["sha256"]
