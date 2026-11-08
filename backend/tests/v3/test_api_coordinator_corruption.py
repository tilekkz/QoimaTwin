"""Known immutable evidence is server corruption; unknown public resources remain 404."""

from copy import deepcopy
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.storage.artifacts import ArtifactCorruption, ArtifactStore
from app.v3.api_coordinator_binding import registration
from app.v3.api_coordinator_inputs import FrozenCoordinatorProfile
from app.v3.api_coordinator_readers import status, verified_artifact, verify_result
from tests.v3.test_api_coordinator_fixtures import CoordinatorApi
from tests.v3.test_api_coordinator_fixtures import registered_hand_api as coordinator_api

__all__ = ["coordinator_api"]


def test_unknown_public_id_is_404_before_any_missing_server_registration(tmp_path: Path) -> None:
    frozen = FrozenCoordinatorProfile("b" * 64, {})
    with pytest.raises(HTTPException) as caught:
        verified_artifact(ArtifactStore(tmp_path), "0" * 64, frozen)
    assert caught.value.status_code == 404


def test_missing_known_registration_is_artifact_corruption(tmp_path: Path) -> None:
    with pytest.raises(ArtifactCorruption):
        registration(ArtifactStore(tmp_path), "a" * 64)


def test_changed_cached_response_cannot_claim_complete_or_free_resources(
    coordinator_api: CoordinatorApi,
) -> None:
    api = coordinator_api
    forged = deepcopy(api.response)
    forged["status"] = "complete"
    forged["resource_drained_tick"] = 158_000_000
    with pytest.raises(ArtifactCorruption):
        verify_result(api.store, forged, api.frozen)


def test_cached_unknown_run_is_corruption_not_an_unknown_public_lookup(
    coordinator_api: CoordinatorApi,
) -> None:
    api = coordinator_api
    forged = {**api.response, "run_id": "0" * 64}
    with pytest.raises(ArtifactCorruption):
        verify_result(api.store, forged, api.frozen)


@pytest.mark.parametrize("damage", ["missing", "changed"])
def test_warm_status_rehashes_native_raw_evidence(
    coordinator_api: CoordinatorApi,
    damage: str,
) -> None:
    api = coordinator_api
    assert status(api.store, api.response["run_id"], api.frozen) == api.response
    index = api.store.read_reference("runs", api.response["run_id"])
    row = next(row for row in index["files"] if row["path"] != "manifest.json")
    path = api.store.path("run_files", row["sha256"])
    original = path.read_bytes()
    try:
        if damage == "missing":
            path.unlink()
        else:
            path.write_bytes(original + b" ")
        with pytest.raises(ArtifactCorruption):
            status(api.store, api.response["run_id"], api.frozen)
    finally:
        path.write_bytes(original)
