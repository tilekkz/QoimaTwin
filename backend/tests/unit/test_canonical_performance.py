"""Encoding optimization keeps the canonical protocol and native JSON boundaries."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.storage.canonical_json import (
    CANONICALIZATION_VERSION,
    canonical_bytes,
    parse_json,
    sha256_hex,
)

TEXT = st.text(st.characters(codec="utf-8"), max_size=20)
SCALAR = (
    st.none()
    | st.booleans()
    | st.integers()
    | st.floats(allow_nan=False, allow_infinity=False)
    | TEXT
)
JSON_VALUES = st.recursive(
    SCALAR,
    lambda child: (
        st.lists(child, max_size=6)
        | st.lists(child, max_size=6).map(tuple)
        | st.dictionaries(TEXT, child, max_size=6)
    ),
    max_leaves=40,
)


@given(JSON_VALUES)
@settings(max_examples=120, deadline=None)
def test_canonical_native_parity(value: Any) -> None:
    expected = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    assert canonical_bytes(value) == expected
    assert sha256_hex(value) == hashlib.sha256(expected).hexdigest()
    assert canonical_bytes(parse_json(expected)) == expected
    assert CANONICALIZATION_VERSION == "qoima-json-v1"


@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan")])
def test_nested_native_nonfinite_errors(value: float) -> None:
    with pytest.raises(ValueError, match="non-finite"):
        canonical_bytes({"nested": ({"values": [value]},)})


@pytest.mark.parametrize("value", [{False: 1}, {None: 1}, {2.5: 1}, Decimal("1"), {1}])
def test_nested_non_json_values(value: object) -> None:
    with pytest.raises(TypeError):
        canonical_bytes({"nested": [value]})


@pytest.mark.parametrize("value", ["1e400", "-1e400", '[{"n":1e400}]', "NaN"])
def test_parse_rejects_overflow_without_post_parse_traversal(value: str) -> None:
    with pytest.raises(ValueError, match="non-finite"):
        parse_json(value)


def test_repeated_container_is_not_a_cycle() -> None:
    shared = {"x": [1, -0.0]}
    assert canonical_bytes([shared, shared]) == b'[{"x":[1,-0.0]},{"x":[1,-0.0]}]'


@pytest.mark.parametrize("kind", ["list", "dict"])
def test_cyclic_containers_fail_with_native_json_error(kind: str) -> None:
    cyclic: Any = [] if kind == "list" else {}
    if kind == "list":
        cyclic.append(cyclic)
    else:
        cyclic["self"] = cyclic
    with pytest.raises(ValueError, match="Circular reference"):
        canonical_bytes(cyclic)
