"""Exact runtime types are part of physical input authority, before canonical projection."""

from collections.abc import Hashable, Mapping
from dataclasses import is_dataclass
from fractions import Fraction
from types import UnionType
from typing import Any, Union, cast, get_args, get_origin

from app.v3.receipt_run_decode import _field_types


def require_types(value: Any, expected: Any) -> None:
    origin, args = get_origin(expected), get_args(expected)
    if origin in (UnionType, Union):
        _union(value, args)
    elif origin in (tuple, frozenset):
        _sequence(value, origin, args)
    elif origin is Mapping:
        if not isinstance(value, Mapping):
            raise ValueError("Physical graph requires an actual mapping")
        for key, child in value.items():
            require_types(key, args[0])
            require_types(child, args[1])
    elif isinstance(expected, type) and is_dataclass(expected):
        if type(value) is not expected:
            raise ValueError("Physical input requires the exact declared record type")
        for key, declared in _field_types(cast(Hashable, expected)).items():
            require_types(getattr(value, key), declared)
    elif expected in (int, bool, str, float, Fraction, type(None)):
        if type(value) is not expected:
            raise ValueError("Physical input requires the exact declared scalar type")
    else:
        raise ValueError("Unsupported declared physical input type")


def _sequence(value: Any, origin: Any, args: tuple[Any, ...]) -> None:
    if type(value) is not origin:
        raise ValueError("Physical input requires its declared immutable collection")
    if origin is frozenset or (len(args) == 2 and args[1] is Ellipsis):
        for child in value:
            require_types(child, args[0])
    else:
        if len(value) != len(args):
            raise ValueError("Physical tuple arity differs")
        for child, expected in zip(value, args, strict=True):
            require_types(child, expected)


def _union(value: Any, choices: tuple[Any, ...]) -> None:
    for candidate in choices:
        try:
            require_types(value, candidate)
            return
        except ValueError:
            continue
    raise ValueError("Physical input does not match its declared optional type")
