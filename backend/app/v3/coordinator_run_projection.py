"""C-only mutable projection; definitions come from exact inputs, never from snapshot claims."""

from dataclasses import fields, is_dataclass
from types import UnionType
from typing import Any, Union, cast, get_args, get_origin

from app.v3.coordinator_models import CoordinatorEvent, CoordinatorOutcome, CoordinatorProfile
from app.v3.coordinator_native_decode import _types, decode, decode_outcome, encode
from app.v3.coordinator_run_definitions import Definitions
from app.v3.flow_profile_sources import _same_types
from app.v3.interface import Json
from app.v3.light_flow_models import FlowEvent
from app.v3.receipt_flow_models import ReceiptFlowEvent
from app.v3.stock_models import Container, StockDelta, UnitToken
from app.v3.stock_receipts import ReceiptDefinition, ReceiptDelta
from app.v3.whole_flow_models import WholeFlowEvent


def project_outcome(profile: CoordinatorProfile, outcome: CoordinatorOutcome) -> Json:
    if type(outcome) is not CoordinatorOutcome:
        raise ValueError("Exact native coordinator outcome required")
    # The typed roundtrip rejects scalar/record aliases before immutable fields are removed.
    decoded = decode_outcome(encode(outcome))
    if not _same_types(outcome, decoded):
        raise ValueError("Native coordinator outcome has a substituted record or scalar type")
    compact = _compact(decoded)
    restored = restore_outcome(profile, compact)
    if encode(restored) != encode(outcome):
        raise ValueError("Native immutable definitions differ from input authority")
    return cast(Json, compact)


def restore_outcome(profile: CoordinatorProfile, value: object) -> CoordinatorOutcome:
    expanded = _expand(CoordinatorOutcome, value, Definitions(profile))
    return decode_outcome(expanded)


def _compact(value: Any) -> Any:
    if type(value) is Container:
        return {
            "container_id": value.container_id,
            "owner_id": value.owner_id,
            "sealed_for": value.sealed_for,
        }
    if type(value) is UnitToken:
        return {"unit_id": value.unit_id}
    if type(value) is ReceiptDefinition:
        return {"receipt_id": value.receipt_id}
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _compact(getattr(value, field.name)) for field in fields(value)}
    if type(value) in (tuple, list):
        return [_compact(item) for item in value]
    return encode(value)


def _expand(expected: Any, value: Any, definitions: Definitions) -> Any:
    origin, args = get_origin(expected), get_args(expected)
    if origin in (UnionType, Union):
        return _union(args, value, definitions)
    if origin in (tuple, frozenset):
        return _sequence(origin, args, value, definitions)
    if isinstance(expected, type) and is_dataclass(expected):
        return _record(expected, value, definitions)
    decode(expected, value)
    return value


def _union(kinds: tuple[Any, ...], value: Any, definitions: Definitions) -> Any:
    for kind in kinds:
        try:
            return _expand(kind, value, definitions)
        except ValueError:
            continue
    raise ValueError("Compact coordinator value has no permitted exact type")


def _sequence(origin: Any, kinds: tuple[Any, ...], value: Any, definitions: Definitions) -> Any:
    if type(value) is not list:
        raise ValueError("Compact coordinator sequence requires an array")
    if origin is frozenset or (len(kinds) == 2 and kinds[1] is Ellipsis):
        return [_expand(kinds[0], item, definitions) for item in value]
    if len(value) != len(kinds):
        raise ValueError("Compact coordinator tuple arity differs")
    return [_expand(kind, item, definitions) for kind, item in zip(kinds, value, strict=True)]


def _record(cls: type[Any], value: Any, definitions: Definitions) -> Json:
    if type(value) is not dict:
        raise ValueError("Compact coordinator record requires an object")
    if cls is Container:
        return definitions.container(value)
    if cls is UnitToken:
        return definitions.unit(value)
    if cls is ReceiptDefinition:
        return definitions.receipt(value)
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
        raise ValueError("Compact coordinator record has missing or unknown fields")
    return {key: _expand(kind, value[key], definitions) for key, kind in types.items()}
