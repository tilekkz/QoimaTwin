"""Exact scalar/record identity, including bool/int/Fraction and tuple distinctions."""

from dataclasses import fields, is_dataclass
from fractions import Fraction
from hashlib import sha256
from typing import Any

from app.storage.canonical_json import canonical_bytes


def typed_record(value: Any) -> Any:
    kind = type(value)
    if kind is Fraction:
        return ["fraction", value.numerator, value.denominator]
    if kind is bytes:
        return ["bytes", len(value), sha256(value).hexdigest()]
    if kind is tuple:
        return ["tuple", [typed_record(item) for item in value]]
    if is_dataclass(value) and not isinstance(value, type):
        return [
            kind.__module__ + "." + kind.__qualname__,
            [[f.name, typed_record(getattr(value, f.name))] for f in fields(value)],
        ]
    if kind in (str, int, float, bool) or value is None:
        return [kind.__name__, value]
    raise ValueError("Unsupported pickup identity type")


def identity(value: object) -> str:
    return sha256(canonical_bytes(typed_record(value))).hexdigest()


def require_same(actual: object, expected: object) -> None:
    if canonical_bytes(typed_record(actual)) != canonical_bytes(typed_record(expected)):
        raise ValueError("Pickup exact typed authority changed")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)
