"""Warm reads keep raw, registration and fresh projection authority inside each request."""

import pytest
from fastapi import HTTPException

from app.storage.artifacts import ArtifactCorruption
from app.storage.canonical_json import canonical_bytes
from app.v3 import api_coordinator_fullness, api_coordinator_readers, api_coordinator_replay
from app.v3 import storage_fullness as fullness_reducer
from app.v3.interface import Json
from tests.v3.test_native_read_context_fixtures import NativeCase, forbid_engine, native_case

__all__ = ["native_case"]


def read(case: NativeCase, operation: str) -> Json:
    if operation == "fullness":
        return api_coordinator_fullness.storage_fullness(case.store, case.identifier, case.frozen)
    return api_coordinator_replay.replay(case.store, case.identifier, 47_000_000, case.frozen)


@pytest.mark.parametrize("operation", ["replay", "fullness"])
@pytest.mark.parametrize("artifact", ["inputs.json", "events/", "result.json"])
def test_each_warm_request_rehashes_original_native_and_outer_bytes(
    native_case: NativeCase, monkeypatch: pytest.MonkeyPatch, operation: str, artifact: str
) -> None:
    case = native_case
    forbid_engine(monkeypatch)
    original_result = canonical_bytes(read(case, operation))
    index = case.store.read_reference("runs", case.identifier)
    rows = [*index["files"], *index["request_files"]]
    row = next(row for row in rows if row["path"].startswith(artifact))
    path = case.store.path("run_files", row["sha256"])
    original = path.read_bytes()
    try:
        path.write_bytes(original + b" ")
        with pytest.raises(ArtifactCorruption):
            read(case, operation)
    finally:
        path.write_bytes(original)
    assert canonical_bytes(read(case, operation)) == original_result


@pytest.mark.parametrize("operation", ["replay", "fullness"])
def test_warm_request_still_checks_registration(
    native_case: NativeCase, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    read(native_case, operation)

    def missing(*_args: object) -> Json:
        raise ArtifactCorruption("fresh registered source unavailable")

    monkeypatch.setattr(api_coordinator_readers, "verified_registration", missing)
    with pytest.raises(ArtifactCorruption, match="source unavailable"):
        read(native_case, operation)


def test_unknown_id_precedes_unavailable_registration(
    native_case: NativeCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*_args: object) -> Json:
        pytest.fail("Unknown public lookup must precede registration")

    monkeypatch.setattr(api_coordinator_readers, "verified_registration", forbidden)
    with pytest.raises(HTTPException) as error:
        api_coordinator_fullness.storage_fullness(native_case.store, "0" * 64, native_case.frozen)
    assert error.value.status_code == 404


def test_fullness_authenticates_capacities_again_on_next_request(
    native_case: NativeCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = read(native_case, "fullness")
    assert first["report"]["at_horizon"]["available"] is False

    def changed(*_args: object) -> None:
        raise ValueError("fresh source capacity authority changed")

    monkeypatch.setattr(fullness_reducer, "source_capacities", changed)
    with pytest.raises(ArtifactCorruption, match="storage observation"):
        read(native_case, "fullness")


def test_mutating_returned_projection_cannot_poison_next_request(native_case: NativeCase) -> None:
    first = read(native_case, "fullness")
    expected = canonical_bytes(first)
    first["report"]["at_end"]["available"] = True
    first["input_hash"] = "0" * 64
    assert canonical_bytes(read(native_case, "fullness")) == expected
