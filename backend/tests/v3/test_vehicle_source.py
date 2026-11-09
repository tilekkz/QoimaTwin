"""Byte identity, strict parsing and source restriction intersections."""

import hashlib
from pathlib import Path

import pytest

from app.v3.vehicle_source import (
    PINNED_SHA256,
    SOURCE_REVISION,
    load_vehicle_adapter,
    verified_json,
)


def test_source_pin_and_documents_are_explicit() -> None:
    assert SOURCE_REVISION == "22296bcf2c6bac5ade4cefc7c05c2b97831ec6ec"
    assert len(PINNED_SHA256) == 6
    assert PINNED_SHA256["vehicle-handling-v3.json"] == (
        "22693087d090a8a45a101d995581573c3b85bf826f67ae7d44fdc524b74cd3e4"
    )


def test_missing_or_modified_source_is_rejected_before_decode(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="source"):
        load_vehicle_adapter(tmp_path)
    directory = tmp_path / "docs/v3/contract-proposals"
    directory.mkdir(parents=True)
    for name in PINNED_SHA256:
        (directory / name).write_bytes(b"{}")
    with pytest.raises(ValueError, match="SHA256"):
        load_vehicle_adapter(tmp_path)


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}', b'{"a":1e400}', b'{"a":NaN}', b"[]"])
def test_matching_hash_does_not_bypass_strict_json(raw: bytes) -> None:
    with pytest.raises(ValueError):
        verified_json(raw, hashlib.sha256(raw).hexdigest())


def test_valid_hash_retains_finite_json() -> None:
    raw = b'{"x":1.25}'
    assert verified_json(raw, hashlib.sha256(raw).hexdigest()) == {"x": 1.25}
