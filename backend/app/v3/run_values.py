"""Exact JSON representations of frozen manual execution values."""

from dataclasses import fields, is_dataclass
from fractions import Fraction
from typing import Any

from app.v3.interface import Json


def wire_value(value: object) -> Any:
    if isinstance(value, Fraction):
        return {"numerator": value.numerator, "denominator": value.denominator}
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: wire_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, frozenset):
        return [wire_value(item) for item in sorted(value)]
    if isinstance(value, tuple):
        return [wire_value(item) for item in value]
    if value is None or type(value) in {str, int, bool}:
        return value
    raise ValueError(f"unsupported manual execution value: {type(value).__name__}")


def record(value: object) -> Json:
    result = wire_value(value)
    if not isinstance(result, dict):
        raise ValueError("manual record must be a dataclass")
    return result


def fraction(value: Json) -> Fraction:
    result = Fraction(value["numerator"], value["denominator"])
    if (result.numerator, result.denominator) != (value["numerator"], value["denominator"]):
        raise ValueError("manual rational must use reduced canonical numerator/denominator")
    return result
