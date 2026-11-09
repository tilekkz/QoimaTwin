"""Real source registration is input validation, never a DES or a hand-profile grant."""

from typing import Any

import pytest

from app.storage.artifacts import ArtifactCorruption, ArtifactStore
from app.v3.api_coordinator_binding import verified_registration
from app.v3.api_coordinator_inputs import FrozenCoordinatorProfile, freeze_profile
from app.v3.coordinator_engine import CoordinatorEngine
from tests.v3.test_coordinator_profile_fixtures import ROOT


@pytest.fixture(scope="module")
def source_registration(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[ArtifactStore, FrozenCoordinatorProfile]:
    store = ArtifactStore(tmp_path_factory.mktemp("coordinator-source-registration"))
    with pytest.MonkeyPatch.context() as patch:

        def forbidden(*args: Any, **kwargs: Any) -> None:
            pytest.fail("Source registration must not execute a coordinator world")

        patch.setattr(CoordinatorEngine, "run", forbidden)
        frozen = freeze_profile(store, ROOT / "data/v3-proposal")
        verified_registration(store, frozen)
    return store, frozen


def test_source_registration_preserves_original_stock_and_all_declared_resources(
    source_registration: tuple[ArtifactStore, FrozenCoordinatorProfile],
) -> None:
    _, frozen = source_registration
    assert frozen.metadata["baseline_hus"] == 530
    assert frozen.metadata["baseline_units"] == 12_256
    assert frozen.metadata["actor_ids_preserved"] == 24
    assert frozen.metadata["station_count"] == 6 and frozen.metadata["cart_count"] == 2
    assert frozen.metadata["full_v3"] is False
    assert frozen.metadata["registry_hash_is_physical_common_identity"] is False


@pytest.mark.parametrize("kind", ["bundle", "profile", "inputs", "source"])
def test_cached_registration_still_requires_every_known_raw_dependency(
    source_registration: tuple[ArtifactStore, FrozenCoordinatorProfile],
    kind: str,
) -> None:
    store, frozen = source_registration
    snapshot = verified_registration(store, frozen)
    keys = {
        "bundle": ("bundles", frozen.bundle_id),
        "profile": ("run_files", snapshot["profile_sha256"]),
        "inputs": ("run_files", snapshot["frozen_inputs"]),
        "source": ("run_files", snapshot["files"][0]["sha256"]),
    }
    path = store.path(*keys[kind])
    raw = path.read_bytes()
    try:
        path.unlink()
        with pytest.raises(ArtifactCorruption):
            verified_registration(store, frozen)
    finally:
        path.write_bytes(raw)
