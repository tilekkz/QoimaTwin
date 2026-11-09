"""Compact N1 state with explicit extension fields; semantic journal validation is separate."""

from typing import Any, cast, get_args, get_origin

from app.v3.coordinator_models import CoordinatorEvent, CoordinatorOutcome, CoordinatorProfile
from app.v3.coordinator_native_decode import _types, encode
from app.v3.coordinator_run_definitions import Definitions
from app.v3.coordinator_run_projection import _compact
from app.v3.coordinator_run_projection import _expand as base_expand
from app.v3.flow_profile_sources import _same_types
from app.v3.interface import Json
from app.v3.light_flow_models import FlowEvent
from app.v3.receipt_flow_models import ReceiptFlowEvent
from app.v3.relocation_native_decode import decode
from app.v3.relocation_observe import RelocationEvent, RelocationOutcome, RelocationSnapshot
from app.v3.whole_flow_models import WholeFlowEvent

_EVENTS = (FlowEvent, ReceiptFlowEvent, WholeFlowEvent, CoordinatorEvent)
_RECORDS = (RelocationEvent, RelocationOutcome, RelocationSnapshot)


def project_outcome(profile: CoordinatorProfile, outcome: CoordinatorOutcome) -> Json:
    if type(outcome) is not RelocationOutcome:
        raise ValueError("Exact relocation outcome required; base promotion must be explicit")
    decoded = decode(RelocationOutcome, encode(outcome))
    if not _same_types(outcome, decoded):
        raise ValueError("Relocation native outcome has a substituted exact type")
    compact = _compact(decoded)
    restored = restore_outcome(profile, compact)
    if encode(restored) != encode(outcome):
        raise ValueError("Relocation immutable definitions differ from original input authority")
    return cast(Json, compact)


def restore_outcome(profile: CoordinatorProfile, value: object) -> RelocationOutcome:
    expanded = _expand(RelocationOutcome, value, Definitions(profile))
    return cast(RelocationOutcome, decode(RelocationOutcome, expanded))


def _expand(expected: Any, value: Any, definitions: Definitions) -> Any:
    if (
        expected in _EVENTS
        and type(value) is dict
        and ("relocation" in value or value.get("work_kind") == "relocation")
    ):
        expected = RelocationEvent
    if expected in _RECORDS:
        return _record(expected, value, definitions)
    origin, args = get_origin(expected), get_args(expected)
    if origin is tuple and len(args) == 2 and args[1] is Ellipsis:
        if type(value) is not list:
            raise ValueError("Compact relocation sequence requires an array")
        return [_expand(args[0], item, definitions) for item in value]
    return base_expand(expected, value, definitions)


def _record(expected: type[Any], value: Any, definitions: Definitions) -> Json:
    if type(value) is not dict:
        raise ValueError("Compact relocation record requires an object")
    if expected is RelocationEvent and value.get("work_kind") != "relocation":
        raise ValueError("Compact relocation event requires its explicit work scope")
    types = _types(expected)
    if value.keys() != types.keys():
        raise ValueError("Compact relocation record has missing or unknown fields")
    return {key: _expand(kind, value[key], definitions) for key, kind in types.items()}
