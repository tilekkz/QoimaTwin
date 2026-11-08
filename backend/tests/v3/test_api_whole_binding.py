"""Frozen registration must retain the actual choices-to-source-envelope relation."""

import pytest

from app.storage.artifacts import ArtifactCorruption, ArtifactStore
from app.v3.api_whole_binding import _validated_registration, verified_registration
from app.v3.api_whole_inputs import FrozenWholeProfile, freeze_profile
from app.v3.settings import default_inputs


@pytest.fixture(scope="module")
def registered(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[ArtifactStore, FrozenWholeProfile]:
    store = ArtifactStore(tmp_path_factory.mktemp("whole-registration"))
    return store, freeze_profile(store, default_inputs())


def test_actual_registered_evidence_and_metadata_are_bound(
    registered: tuple[ArtifactStore, FrozenWholeProfile],
) -> None:
    store, frozen = registered
    snapshot = verified_registration(store, frozen)
    assert snapshot["input_hash"] == frozen.metadata["input_hash"]
    assert frozen.metadata["baseline_hus"] == 530
    assert frozen.metadata["baseline_units"] == 12256
    assert frozen.metadata["receipt_units"] == 24
    assert frozen.metadata["whole_job_count"] == 1
    assert frozen.metadata["actor_ids_preserved"] == 24


def test_mutated_metadata_cannot_inherit_registration_authority(
    registered: tuple[ArtifactStore, FrozenWholeProfile],
) -> None:
    store, frozen = registered
    changed = FrozenWholeProfile(frozen.bundle_id, {**frozen.metadata, "input_hash": "a" * 64})
    with pytest.raises(ArtifactCorruption):
        verified_registration(store, changed)


def test_warm_registration_cache_still_rehashes_its_source_files(
    registered: tuple[ArtifactStore, FrozenWholeProfile],
) -> None:
    store, frozen = registered
    snapshot = verified_registration(store, frozen)
    path = store.path("run_files", snapshot["files"][0]["sha256"])
    raw = path.read_bytes()
    try:
        path.write_bytes(b"corrupted registered source")
        with pytest.raises(ArtifactCorruption):
            verified_registration(store, frozen)
    finally:
        path.write_bytes(raw)


@pytest.mark.parametrize("warm", [False, True])
def test_missing_known_registration_is_corruption_before_cached_metadata(
    registered: tuple[ArtifactStore, FrozenWholeProfile],
    warm: bool,
) -> None:
    store, frozen = registered
    _validated_registration.cache_clear()
    if warm:
        verified_registration(store, frozen)
    path = store.path("bundles", frozen.bundle_id)
    raw = path.read_bytes()
    try:
        path.unlink()
        with pytest.raises(ArtifactCorruption, match="unavailable"):
            verified_registration(store, frozen)
    finally:
        path.write_bytes(raw)
