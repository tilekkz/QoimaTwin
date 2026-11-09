"""Known run-index corruption remains a server artifact error after a warm read."""

from tests.v3.test_api_coordinator_fixtures import CoordinatorApi
from tests.v3.test_api_coordinator_fixtures import registered_hand_api as coordinator_api

__all__ = ["coordinator_api"]


def test_replay_rejects_corrupt_known_index_as_artifact_corruption(
    coordinator_api: CoordinatorApi,
) -> None:
    api = coordinator_api
    assert api.client.get(api.base + "/replay?tick=102000000").status_code == 200
    reference = api.store.path("runs", api.response["run_id"])
    original = reference.read_bytes()
    try:
        reference.write_bytes(b"{")
        response = api.client.get(api.base + "/replay?tick=104000000")
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "artifact_corruption"
        assert len(api.processor.calls) == 1
    finally:
        reference.write_bytes(original)
