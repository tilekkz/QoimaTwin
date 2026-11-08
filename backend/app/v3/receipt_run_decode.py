"""Strict data-only native JSON reconstruction for an already performed receipt run."""

from collections.abc import Hashable
from dataclasses import fields, is_dataclass
from fractions import Fraction
from functools import cache
from types import UnionType
from typing import Any, Literal, Union, cast, get_args, get_origin, get_type_hints

from app.v3.flow_profile_wire import record
from app.v3.light_flow_models import FlowEvent
from app.v3.receipt_flow_models import ReceiptFlowEvent, ReceiptFlowOutcome
from app.v3.stock_models import StockDelta
from app.v3.stock_receipts import ReceiptDelta


def decode_outcome(value: object) -> ReceiptFlowOutcome:
    """Deserialize native values only; publication validation remains mandatory afterwards."""
    return cast(ReceiptFlowOutcome, _decode(ReceiptFlowOutcome, value))


def _decode(expected: Any, value: Any) -> Any:
    origin, args = get_origin(expected), get_args(expected)
    if origin in (UnionType, Union):
        return _union(args, value)
    if origin is tuple:
        if type(value) is not list:
            raise ValueError("Native tuple requires a JSON array")
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(_decode(args[0], v) for v in value)
        if len(value) != len(args):
            raise ValueError("Native tuple arity differs")
        return tuple(_decode(t, v) for t, v in zip(args, value, strict=True))
    if origin is Literal:
        if not any(type(value) is type(v) and value == v for v in args):
            raise ValueError("Native literal differs")
        return value
    if expected is Fraction:
        return _fraction(value)
    if expected in (int, bool, str, float, type(None)):
        if type(value) is not expected:
            raise ValueError("Native scalar has the wrong exact type")
        return value
    if isinstance(expected, type) and is_dataclass(expected):
        return _dataclass(expected, value)
    raise ValueError("Unsupported native receipt field type")


def _fraction(value: Any) -> Fraction:
    if type(value) is not dict or set(value) != {"numerator", "denominator"}:
        raise ValueError("Native rational requires exactly numerator and denominator")
    n, d = value["numerator"], value["denominator"]
    if type(n) is not int or type(d) is not int or d <= 0:
        raise ValueError("Native rational requires exact integers and positive denominator")
    result = Fraction(n, d)
    if record(result) != value:
        raise ValueError("Native rational must be canonically reduced")
    return result


def _union(types: tuple[Any, ...], value: Any) -> Any:
    for candidate in types:
        try:
            return _decode(candidate, value)
        except ValueError:
            continue
    raise ValueError("Native value does not match any permitted field type")


@cache
def _field_types(cls: Any) -> dict[str, Any]:
    hints = get_type_hints(cls)
    return {field.name: hints[field.name] for field in fields(cls)}


def _dataclass(cls: type[Any], value: Any) -> Any:
    if type(value) is not dict:
        raise ValueError("Native record requires a JSON object")
    if cls is FlowEvent and "receipt" in value:
        cls = ReceiptFlowEvent
    if cls is StockDelta and "created_tokens" in value:
        cls = ReceiptDelta
    field_types = _field_types(cast(Hashable, cls))
    if value.keys() != field_types.keys():
        raise ValueError("Native record contains missing or unknown fields")
    return cls(**{key: _decode(expected, value[key]) for key, expected in field_types.items()})
