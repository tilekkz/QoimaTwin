"""Exact data-only coordinator reconstruction; no engine, history inference or legacy projection."""

import math
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from fractions import Fraction
from types import UnionType
from typing import Any, Literal, Union, cast, get_args, get_origin, get_type_hints

from app.v3.coordinator_models import CoordinatorEvent, CoordinatorOutcome
from app.v3.light_flow_models import FlowEvent
from app.v3.receipt_flow_models import ReceiptFlowEvent
from app.v3.runtime_graph import Arc, DirectedGraph
from app.v3.stock_models import StockDelta
from app.v3.stock_receipts import ReceiptDelta
from app.v3.whole_flow_models import WholeFlowEvent

_TYPE_HINTS: dict[type[Any], dict[str, Any]] = {}


def decode_outcome(value: object) -> CoordinatorOutcome:
    return cast(CoordinatorOutcome, decode(CoordinatorOutcome, value))


def encode(value: Any) -> Any:
    if type(value) is Fraction:
        return {"numerator": value.numerator, "denominator": value.denominator}
    if type(value) is DirectedGraph:
        return {
            "graph_id": value.graph_id,
            "node_ids": list(value.node_ids),
            "arcs": encode(value.arcs),
        }
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: encode(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        if any(type(key) is not str for key in value):
            raise ValueError("Coordinator record keys must be exact strings")
        return {key: encode(child) for key, child in value.items()}
    if type(value) in (tuple, list):
        return [encode(child) for child in value]
    if type(value) is frozenset:
        return [encode(child) for child in sorted(value)]
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    raise ValueError("Unsupported coordinator projection value")


def decode(expected: Any, value: Any) -> Any:
    origin, args = get_origin(expected), get_args(expected)
    if origin in (UnionType, Union):
        return _union(args, value)
    if origin in (tuple, frozenset):
        return _sequence(origin, args, value)
    if origin is Literal:
        if not any(type(value) is type(item) and value == item for item in args):
            raise ValueError("Coordinator native literal differs")
        return value
    if expected is Fraction:
        return _fraction(value)
    if expected in (int, bool, str, float, type(None)):
        if type(value) is not expected or (expected is float and not math.isfinite(value)):
            raise ValueError("Coordinator native scalar has the wrong exact type")
        return value
    if isinstance(expected, type) and is_dataclass(expected):
        return _record(expected, value)
    raise ValueError("Unsupported coordinator native field type")


def _fraction(value: Any) -> Fraction:
    if type(value) is not dict or set(value) != {"numerator", "denominator"}:
        raise ValueError("Coordinator native fraction has incorrect fields")
    numerator, denominator = value["numerator"], value["denominator"]
    if type(numerator) is not int or type(denominator) is not int or denominator <= 0:
        raise ValueError("Coordinator native fraction requires exact integer fields")
    result = Fraction(numerator, denominator)
    if result.numerator != numerator or result.denominator != denominator:
        raise ValueError("Coordinator native fraction must be reduced")
    return result


def _sequence(origin: Any, args: tuple[Any, ...], value: Any) -> Any:
    if type(value) is not list:
        raise ValueError("Coordinator native sequence requires an array")
    if origin is frozenset:
        result = frozenset(decode(args[0], item) for item in value)
        if len(result) != len(value) or sorted(result) != value:
            raise ValueError("Coordinator native set must be unique and sorted")
        return result
    if len(args) == 2 and args[1] is Ellipsis:
        return tuple(decode(args[0], item) for item in value)
    if len(value) != len(args):
        raise ValueError("Coordinator native tuple arity differs")
    return tuple(decode(kind, item) for kind, item in zip(args, value, strict=True))


def _union(kinds: tuple[Any, ...], value: Any) -> Any:
    for kind in kinds:
        try:
            return decode(kind, value)
        except ValueError:
            continue
    raise ValueError("Coordinator native value does not match a permitted exact type")


def _types(cls: type[Any]) -> dict[str, Any]:
    if cls not in _TYPE_HINTS:
        hints = get_type_hints(cls)
        _TYPE_HINTS[cls] = {field.name: hints[field.name] for field in fields(cls)}
    return _TYPE_HINTS[cls]


def _record(cls: type[Any], value: Any) -> Any:
    if type(value) is not dict:
        raise ValueError("Coordinator native record requires an object")
    if cls is DirectedGraph:
        return _graph(value)
    if cls in (FlowEvent, ReceiptFlowEvent, WholeFlowEvent):
        if "work_kind" in value:
            cls = CoordinatorEvent
        elif "whole_order" in value:
            cls = WholeFlowEvent
        elif "receipt" in value:
            cls = ReceiptFlowEvent
    if cls is StockDelta and "created_tokens" in value:
        cls = ReceiptDelta
    types = _types(cls)
    if value.keys() != types.keys():
        raise ValueError("Coordinator native record has missing or unknown fields")
    return cls(**{key: decode(kind, value[key]) for key, kind in types.items()})


def _graph(value: Any) -> DirectedGraph:
    if set(value) != {"graph_id", "node_ids", "arcs"}:
        raise ValueError("Coordinator graph has missing or unknown public fields")
    return DirectedGraph(
        decode(str, value["graph_id"]),
        decode(tuple[str, ...], value["node_ids"]),
        decode(tuple[Arc, ...], value["arcs"]),
    )
