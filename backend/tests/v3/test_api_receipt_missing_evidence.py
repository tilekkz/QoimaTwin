"""Missing registered server evidence is artifact corruption, including after cache reuse."""

from pathlib import Path

import pytest
from fastapi import HTTPException

from app.storage.artifacts import ArtifactCorruption
from app.v3.api_receipt_readers import _validated, file_bytes, run_index, status
from tests.v3.test_api_receipt_independent_fixtures import HandRegistration, registered_hand


@pytest.fixture(scope="module")
def registration(tmp_path_factory: pytest.TempPathFactory) -> HandRegistration:
    return registered_hand(tmp_path_factory.mktemp("receipt-evidence"))


def evidence_path(registration: HandRegistration, kind: str) -> Path:
    store, frozen = registration.store, registration.frozen
    if kind == "bundle":
        return store.path("bundles", frozen.bundle_id)
    snapshot = store.read_json("bundles", frozen.bundle_id)
    key = (
        registration.evidence_hash
        if kind == "source"
        else snapshot["profile_sha256" if kind == "profile" else "frozen_inputs"]
    )
    return store.path("run_files", key)


@pytest.mark.parametrize(
    "warm,kind",
    [(warm, kind) for warm in (False, True) for kind in ("bundle", "profile", "frozen", "source")],
)
def test_missing_registered_evidence_is_corruption_before_and_after_cache(
    registration: HandRegistration, warm: bool, kind: str
) -> None:
    store, frozen, identifier = (
        registration.store,
        registration.frozen,
        registration.response["run_id"],
    )
    if warm:
        assert status(store, identifier, frozen)["status"] == "partial"
        assert _validated.cache_info().currsize > 0
    else:
        _validated.cache_clear()
    path = evidence_path(registration, kind)
    raw = path.read_bytes()
    path.unlink()
    try:
        with pytest.raises(ArtifactCorruption):
            status(store, identifier, frozen)
    finally:
        path.write_bytes(raw)
    assert path.read_bytes() == raw


def test_unknown_public_run_and_unlisted_file_remain_not_found(
    registration: HandRegistration,
) -> None:
    store, frozen = registration.store, registration.frozen
    unknown = "f" * 64
    assert unknown != registration.response["run_id"]
    with pytest.raises(HTTPException) as run_error:
        status(store, unknown, frozen)
    assert run_error.value.status_code == 404
    index = run_index(store, registration.response["run_id"], frozen)
    assert unknown not in {row["sha256"] for row in index["files"]}
    with pytest.raises(HTTPException) as file_error:
        file_bytes(store, index, unknown)
    assert file_error.value.status_code == 404
