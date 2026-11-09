"""Recomputed reference hashes cannot authorize changed native or outer evidence inventories."""

from copy import deepcopy

import pytest

from app.storage.artifacts import ArtifactCorruption
from app.storage.canonical_json import canonical_bytes, sha256_hex
from app.v3.api_coordinator_readers import status
from tests.v3.test_api_coordinator_fixtures import CoordinatorApi
from tests.v3.test_api_coordinator_fixtures import registered_hand_api as coordinator_api

__all__ = ["coordinator_api"]


@pytest.mark.parametrize("change", ["missing_native", "other_bundle", "outer_alias", "bool_length"])
def test_rehashed_index_cannot_weaken_registered_native_evidence(
    coordinator_api: CoordinatorApi,
    change: str,
) -> None:
    api = coordinator_api
    assert status(api.store, api.response["run_id"], api.frozen) == api.response
    path = api.store.path("runs", api.response["run_id"])
    original = path.read_bytes()
    index = deepcopy(api.store.read_reference("runs", api.response["run_id"]))
    if change == "missing_native":
        index["files"] = [row for row in index["files"] if row["path"] != "inputs.json"]
    elif change == "other_bundle":
        index["input_bundle_id"] = "d" * 64
    elif change == "outer_alias":
        index["request_files"][0]["path"] = index["request_files"][1]["path"]
    else:
        index["files"][0]["bytes"] = True
    try:
        path.write_bytes(canonical_bytes({"value": index, "content_sha256": sha256_hex(index)}))
        with pytest.raises(ArtifactCorruption):
            status(api.store, api.response["run_id"], api.frozen)
    finally:
        path.write_bytes(original)
