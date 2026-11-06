"""Canonical JSON v1: Python repr floats, integer-preserving, ordered arrays.

Callers sort set-like arrays by ID; serialization preserves all array ordering.
Parsing must use parse_json to detect duplicate keys before they are lost.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

CANONICALIZATION_VERSION = "qoima-json-v1"


def _validate(obj: object) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if not isinstance(key, str):
                raise TypeError("JSON object keys must be strings")
            _validate(value)
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            _validate(value)
    elif isinstance(obj, float):
        if not math.isfinite(obj):
            raise ValueError("non-finite JSON number")
    elif obj is not None and not isinstance(obj, (str, int, bool)):
        raise TypeError(f"unsupported JSON value: {type(obj).__name__}")


def canonical_bytes(obj: object) -> bytes:
    """Encode UTF-8; stdlib JSON uses float repr, without converting ints to floats."""
    _validate(obj)
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha256_hex(obj: object) -> str:
    """Hash canonical JSON, not a file or an already-serialized JSON string."""
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> Any:
    raise ValueError(f"non-finite JSON number: {value}")


def parse_json(text: str | bytes) -> Any:
    """Parse strict JSON, rejecting nested duplicate keys and overflowing numbers."""
    result = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    _validate(result)
    return result
