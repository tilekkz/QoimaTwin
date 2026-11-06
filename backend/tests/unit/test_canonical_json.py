"""Canonical bytes preserve numeric types and reject ambiguous or non-finite JSON."""

from __future__ import annotations

import hashlib

import pytest

from app.storage.canonical_json import canonical_bytes, parse_json, sha256_hex


def test_canonical_bytes_and_hash() -> None:
    expected = '{"a":1,"b":1.0,"c":"Қойма","d":[2,1]}'.encode()
    data = {"d": [2, 1], "c": "Қойма", "b": 1.0, "a": 1}
    assert canonical_bytes(data) == expected
    assert sha256_hex(data) == hashlib.sha256(expected).hexdigest()
    assert canonical_bytes(dict(reversed(list(data.items())))) == expected
    assert canonical_bytes(parse_json(expected)) == expected
    assert canonical_bytes(0.12345678901234568) == repr(0.12345678901234568).encode()


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_reject_nonfinite(value: float) -> None:
    with pytest.raises(ValueError, match="non-finite"):
        canonical_bytes({"nested": [value]})


@pytest.mark.parametrize(
    "text",
    ['{"x":1,"x":2}', '{"nested":{"x":1,"x":2}}', '{"x":1,"\\u0078":2}'],
)
def test_reject_duplicate_keys(text: str) -> None:
    with pytest.raises(ValueError, match="duplicate JSON key"):
        parse_json(text)


@pytest.mark.parametrize("text", ["NaN", "Infinity", "-Infinity", "1e999", "[1e999]"])
def test_parse_rejects_nonfinite(text: str) -> None:
    with pytest.raises(ValueError, match="non-finite"):
        parse_json(text)


@pytest.mark.parametrize("value", [{1: "ambiguous key"}, {1, 2}, object()])
def test_reject_non_json_values(value: object) -> None:
    with pytest.raises(TypeError):
        canonical_bytes(value)
