"""Raw pinned worker bytes and exact F02/FL02 source identity are mandatory."""

from dataclasses import replace
from pathlib import Path
from shutil import copytree

import pytest

from app.v3.pallet_operator_fit_source import load_operator_fit_source, verify_operator_fit_source
from app.v3.pallet_outbound_pickup_identity import identity
from tests.v3.test_pallet_operator_fit_fixtures import ASSETS, BACKEND, source


def test_source_identity_does_not_depend_on_asset_path(tmp_path: Path) -> None:
    copied = copytree(ASSETS, tmp_path / "relocated-assets")
    original = source()
    assert load_operator_fit_source(BACKEND / "data", copied) == original
    assert len(original.worker_raw) == 181828
    verify_operator_fit_source(original)


def test_changed_raw_worker_cannot_be_rehashed_into_authority() -> None:
    original = source()
    changed = replace(original, worker_raw=original.worker_raw[:-1] + b"x", source_hash="")
    changed = replace(changed, source_hash=identity(changed))
    with pytest.raises(ValueError, match="worker"):
        verify_operator_fit_source(changed)


def test_changed_raw_provenance_cannot_be_rehashed_into_authority() -> None:
    original = source()
    changed = replace(original, provenance_raw=original.provenance_raw + b" ", source_hash="")
    changed = replace(changed, source_hash=identity(changed))
    with pytest.raises(ValueError, match="provenance"):
        verify_operator_fit_source(changed)


def test_mutable_byte_alias_rejects() -> None:
    original = source()
    changed = replace(original, worker_raw=bytearray(original.worker_raw))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="Exact"):
        verify_operator_fit_source(changed)


def test_missing_raw_source_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"missing|unreadable"):
        load_operator_fit_source(BACKEND / "data", tmp_path)
