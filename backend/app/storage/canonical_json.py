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
_CONTAINERS = (dict, list, tuple)


def _validate_keys(obj: object) -> None:
    """Check the one ambiguity json.dumps accepts: non-string object keys."""
    pending = [obj]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            for key, item in value.items():
                if not isinstance(key, str):
                    raise TypeError("JSON object keys must be strings")
                if isinstance(item, _CONTAINERS):
                    pending.append(item)
        elif isinstance(value, (list, tuple)):
            pending.extend(item for item in value if isinstance(item, _CONTAINERS))


def canonical_bytes(obj: object) -> bytes:
    """Encode UTF-8; stdlib JSON uses float repr, without converting ints to floats."""
    try:
        encoded = json.dumps(
            obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
    except ValueError as exc:
        if str(exc).startswith("Out of range float values"):
            raise ValueError("non-finite JSON number") from exc
        raise
    # Encode first: native circular-reference detection makes the key-only walk safe.
    _validate_keys(obj)
    return encoded.encode("utf-8")


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


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"non-finite JSON number: {value}")
    return number


def parse_json(text: str | bytes) -> Any:
    """Parse strict JSON, rejecting nested duplicate keys and overflowing numbers."""
    return json.loads(
        text,
        object_pairs_hook=_unique_object,
        parse_constant=_reject_constant,
        parse_float=_finite_float,
    )
