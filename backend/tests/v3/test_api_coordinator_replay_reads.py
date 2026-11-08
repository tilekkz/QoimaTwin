"""Prewritten HTTP settled seeks use observed facts, never a second scheduler."""

import pytest

from app.v3.coordinator_engine import CoordinatorEngine
from tests.v3.test_api_coordinator_fixtures import CoordinatorApi
from tests.v3.test_api_coordinator_fixtures import registered_hand_api as coordinator_api

__all__ = ["coordinator_api"]


def test_arbitrary_seek_keeps_paid_future_return_and_matches_exact_capture(
    coordinator_api: CoordinatorApi,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("A replay read cannot run the coordinator")

    monkeypatch.setattr(CoordinatorEngine, "run", forbidden)
    api = coordinator_api
    response = api.client.get(api.base + "/replay", params={"tick": "158000000"})
    assert response.status_code == 200, response.text
    value = response.json()
    checkpoint = api.client.get(api.base + "/checkpoint", params={"tick": "158000000"})
    assert checkpoint.status_code == 200
    assert value["snapshot"] == checkpoint.json()["checkpoint"]
    assert value["tick"] == 158_000_000 == value["observed_until_tick"]
    assert value["last_seq"] == value["snapshot"]["last_seq"]
    assert value["input_hash"] == api.response["input_hash"]
    workers = {w["actor_id"]: w for w in value["snapshot"]["workers"]}
    assert len(workers) == 24
    for actor in ("P11", "P12"):
        assert workers[actor]["operation"]["kind"] == "role_return"
        assert workers[actor]["operation"]["planned_end_tick"] == 160_000_000
    assert len(api.processor.calls) == 1


def test_backward_repeated_seek_applies_inclusive_events_without_rewriting_run(
    coordinator_api: CoordinatorApi,
) -> None:
    api = coordinator_api
    manifest_before = api.client.get(api.base + "/manifest").content
    results = []
    for tick in (158_000_000, 102_000_000, 104_000_000, 158_000_000):
        response = api.client.get(api.base + "/replay", params={"tick": str(tick)})
        assert response.status_code == 200, response.text
        results.append(response.json())
    assert results[0] == results[-1]
    at102, at104 = results[1]["snapshot"], results[2]["snapshot"]
    assert {r["status"] for r in at102["roles"]} == {"outward"}
    assert {r["intent_id"]: r["status"] for r in at104["roles"]} == {
        "I11": "active",
        "I12": "outward",
    }
    helpers = {w["actor_id"]: w for w in at102["workers"]}
    assert helpers["P11"]["paid_ticks"] == helpers["P12"]["paid_ticks"] == 2_000_000
    assert api.client.get(api.base + "/checkpoint", params={"tick": "104000000"}).status_code == 422
    assert api.client.get(api.base + "/manifest").content == manifest_before
    assert api.client.get(api.base).json() == api.response


def test_replay_scope_and_mutable_projection_do_not_duplicate_definitions_or_history(
    coordinator_api: CoordinatorApi,
) -> None:
    response = coordinator_api.client.get(coordinator_api.base + "/replay", params={"tick": "0"})
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["reader_version"] == "qoima-coordinator-settled-replay-api-0.1.0"
    assert value["scope"] == "verified_native_settled_state"
    assert value["state_boundary"] == "after_all_observed_events_with_tick_lte_T"
    assert value["reader_capabilities"] == {
        "arbitrary_settled_state": True,
        "engine_restore": False,
        "geometric_interpolation": False,
        "full_v3": False,
    }
    state = value["snapshot"]
    assert "events" not in state and "checkpoints" not in state and "history" not in state
    for inventory in (state["stock"], state["inventory"]):
        assert "units" not in inventory
        assert all(
            set(unit) == {"unit_id", "container_id", "position"} for unit in inventory["locations"]
        )
        assert all(
            set(c) == {"container_id", "owner_id", "sealed_for"} for c in inventory["containers"]
        )
