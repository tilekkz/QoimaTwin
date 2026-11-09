"""Closed opt-in N1 native records; decoding alone is not semantic acceptance."""

from typing import Any, get_args, get_origin

from app.v3.coordinator_models import CoordinatorEvent
from app.v3.coordinator_native_decode import _types
from app.v3.coordinator_native_decode import decode as base_decode
from app.v3.light_flow_models import FlowEvent
from app.v3.receipt_flow_models import ReceiptFlowEvent
from app.v3.relocation_observe import RelocationEvent, RelocationOutcome, RelocationSnapshot
from app.v3.whole_flow_models import WholeFlowEvent

_EVENTS = (FlowEvent, ReceiptFlowEvent, WholeFlowEvent, CoordinatorEvent)
_RECORDS = (RelocationEvent, RelocationOutcome, RelocationSnapshot)


def decode(expected: Any, value: Any) -> Any:
    if (
        expected in _EVENTS
        and type(value) is dict
        and ("relocation" in value or value.get("work_kind") == "relocation")
    ):
        expected = RelocationEvent
    if expected in _RECORDS:
        return _record(expected, value)
    origin, args = get_origin(expected), get_args(expected)
    if origin is tuple and len(args) == 2 and args[1] is Ellipsis:
        if type(value) is not list:
            raise ValueError("Relocation native sequence requires an array")
        return tuple(decode(args[0], item) for item in value)
    return base_decode(expected, value)


def _record(expected: type[Any], value: Any) -> Any:
    if type(value) is not dict:
        raise ValueError("Relocation native record requires an object")
    if expected is RelocationEvent and value.get("work_kind") != "relocation":
        raise ValueError("Relocation native event requires its explicit work scope")
    types = _types(expected)
    if value.keys() != types.keys():
        raise ValueError("Relocation native record has missing or unknown fields")
    return expected(**{key: decode(kind, value[key]) for key, kind in types.items()})
