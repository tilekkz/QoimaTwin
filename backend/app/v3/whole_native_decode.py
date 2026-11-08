"""Strict data-only whole values; decoding never restores or executes an engine."""

from collections.abc import Hashable
from dataclasses import is_dataclass
from fractions import Fraction
from types import UnionType
from typing import Any, Literal, Union, cast, get_args, get_origin

from app.v3.light_flow_models import FlowEvent
from app.v3.receipt_flow_models import ReceiptFlowEvent
from app.v3.receipt_run_decode import _field_types, _fraction
from app.v3.stock_models import StockDelta
from app.v3.stock_receipts import ReceiptDelta
from app.v3.whole_flow_models import WholeFlowEvent, WholeFlowOutcome


def decode_outcome(value: object) -> WholeFlowOutcome:
    return cast(WholeFlowOutcome, decode(WholeFlowOutcome, value))


def decode(expected: Any, value: Any) -> Any:
    origin, args = get_origin(expected), get_args(expected)
    if origin in (UnionType, Union):
        return _union(args, value)
    if origin in (tuple, frozenset):
        return _sequence(origin, args, value)
    if origin is Literal:
        if not any(type(value) is type(v) and value == v for v in args):
            raise ValueError("Whole native literal differs")
        return value
    if expected is Fraction:
        return _fraction(value)
    if expected in (int, bool, str, float, type(None)):
        if type(value) is not expected:
            raise ValueError("Whole native scalar has the wrong exact type")
        return value
    if isinstance(expected, type) and is_dataclass(expected):
        return _dataclass(expected, value)
    raise ValueError("Unsupported whole native field type")


def _sequence(origin: Any, args: tuple[Any, ...], value: Any) -> Any:
    if type(value) is not list:
        raise ValueError("Whole native sequence requires a JSON array")
    if origin is frozenset:
        result = frozenset(decode(args[0], v) for v in value)
        if len(result) != len(value) or sorted(result) != value:
            raise ValueError("Whole native set requires sorted unique values")
        return result
    if len(args) == 2 and args[1] is Ellipsis:
        return tuple(decode(args[0], v) for v in value)
    if len(value) != len(args):
        raise ValueError("Whole native tuple arity differs")
    return tuple(decode(t, v) for t, v in zip(args, value, strict=True))


def _union(types: tuple[Any, ...], value: Any) -> Any:
    for candidate in types:
        try:
            return decode(candidate, value)
        except ValueError:
            continue
    raise ValueError("Whole native value does not match a permitted field type")


def _dataclass(cls: type[Any], value: Any) -> Any:
    if type(value) is not dict:
        raise ValueError("Whole native record requires a JSON object")
    if cls in (FlowEvent, ReceiptFlowEvent):
        if "whole_order" in value:
            cls = WholeFlowEvent
        elif "receipt" in value:
            cls = ReceiptFlowEvent
    if cls is StockDelta and "created_tokens" in value:
        cls = ReceiptDelta
    types = _field_types(cast(Hashable, cls))
    if value.keys() != types.keys():
        raise ValueError("Whole native record has missing or unknown fields")
    return cls(**{key: decode(expected, value[key]) for key, expected in types.items()})
