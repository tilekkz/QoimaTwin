"""Independent exact-type boundaries for opt-in relocation event records."""

from copy import deepcopy
from typing import Any

import pytest

from app.v3.coordinator_native_decode import decode as coordinator_decode
from app.v3.coordinator_native_decode import encode
from app.v3.light_flow_models import FlowEvent
from app.v3.relocation_native_decode import decode
from app.v3.relocation_observe import RelocationEvent, RelocationView


def event_record() -> dict[str, Any]:
    view = RelocationView(
        "MOVE1", "HU1", "S01", "source", "target", "carrying", 0, 4, None, None, 2, None
    )
    return dict(encode(RelocationEvent(1, 4, "relocation_taken", "MOVE1", relocation=view)))


def test_extension_event_roundtrip_retains_its_exact_record_and_view() -> None:
    value = event_record()
    result = decode(FlowEvent, value)
    assert type(result) is RelocationEvent
    assert type(result.relocation) is RelocationView
    assert result.relocation.taken_tick == 4
    assert result.relocation.placed_tick is None
    assert encode(result) == value
    with pytest.raises(ValueError):
        coordinator_decode(FlowEvent, value)


@pytest.mark.parametrize("field", ["seq", "tick", "taken_tick", "completed_steps"])
def test_boolean_aliases_cannot_replace_integer_progress(field: str) -> None:
    value = event_record()
    target = value if field in {"seq", "tick"} else value["relocation"]
    target[field] = False
    with pytest.raises(ValueError):
        decode(FlowEvent, value)


@pytest.mark.parametrize("change", ["unknown", "missing", "wrong_scope", "wrong_view"])
def test_extension_has_closed_fields_and_explicit_scope(change: str) -> None:
    value = deepcopy(event_record())
    if change == "unknown":
        value["unexpected"] = 0
    elif change == "missing":
        del value["relocation"]
    elif change == "wrong_scope":
        value["work_kind"] = "role_intent"
    else:
        value["relocation"]["hu_id"] = 7
    with pytest.raises(ValueError):
        decode(FlowEvent, value)


def test_regular_base_event_keeps_its_original_exact_type_and_bytes() -> None:
    event = FlowEvent(0, 0, "created", "O1")
    value = encode(event)
    decoded = decode(FlowEvent, value)
    assert type(decoded) is FlowEvent
    assert decoded == event
    assert encode(decoded) == value
