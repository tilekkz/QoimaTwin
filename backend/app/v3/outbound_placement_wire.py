"""Closed canonical decision projection; source stock retains its complete native bytes."""

from dataclasses import fields, is_dataclass
from fractions import Fraction
from typing import Any

from app.storage.canonical_json import parse_json
from app.v3.outbound_placement_models import (
    SELECTION_POLICY,
    VERSION,
    N1PlacementDecision,
)


def record(value: Any) -> Any:
    if type(value) is Fraction:
        return [value.numerator, value.denominator]
    if type(value) is bytes:
        return value.decode("utf-8")
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: record(getattr(value, f.name)) for f in fields(value)}
    if type(value) is tuple:
        return [record(item) for item in value]
    if value is None or type(value) in (str, int, bool):
        return value
    raise ValueError("Unsupported placement record type")


def decision_record(value: N1PlacementDecision) -> dict[str, Any]:
    return {
        "schema_version": VERSION,
        "selection_policy": SELECTION_POLICY,
        "stock_inputs": parse_json(value.stock.frozen_bytes),
        "stock_input_hash": value.stock.input_hash,
        "choices": record(value.choices),
        "evaluations": record(value.evaluations),
        "selected": record(value.selected),
        "no_op": value.no_op,
        "selection_reason": value.selection_reason,
        "placements": record(value.placements),
        "operational_admission": False,
        "full_n1_acceptance": False,
    }
