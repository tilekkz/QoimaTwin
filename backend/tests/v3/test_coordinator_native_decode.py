"""The coordinator decoder retains its own full native type; no old single-cart projection."""

from copy import deepcopy

import pytest

from app.v3.coordinator_native_decode import decode_outcome
from app.v3.flow_profile_wire import record
from tests.v3.test_coordinator_metrics import role_case
from tests.v3.test_receipt_flow_fixtures import SECOND


def test_native_roundtrip_preserves_roles_open_motion_and_full_cart_fields() -> None:
    _, outcome = role_case(105 * SECOND)
    raw = record(outcome)
    restored = decode_outcome(raw)
    assert type(restored) is type(outcome)
    assert record(restored) == raw
    assert restored.at_end.roles[1].activated_tick is None
    assert len(restored.at_end.carts) == 1
    assert len(restored.at_end.workers) == 24


@pytest.mark.parametrize("field", ["carts", "unit_progress", "cart_releases", "role_bindings"])
def test_missing_new_state_field_is_not_accepted_as_legacy_whole_state(field: str) -> None:
    _, outcome = role_case(105 * SECOND)
    raw = deepcopy(record(outcome))
    del raw["at_end"][field]
    with pytest.raises(ValueError, match="fields"):
        decode_outcome(raw)


def test_boolean_tick_and_numeric_equal_fraction_clock_do_not_coerce() -> None:
    _, outcome = role_case(105 * SECOND)
    for wrong in (True, {"numerator": 105 * SECOND, "denominator": 1}):
        raw = deepcopy(record(outcome))
        raw["at_end"]["tick"] = wrong
        with pytest.raises(ValueError, match="exact type"):
            decode_outcome(raw)


def test_unknown_coordinator_event_fields_are_rejected() -> None:
    _, outcome = role_case(105 * SECOND)
    raw = deepcopy(record(outcome))
    raw["events"][0]["caller_verified"] = True
    with pytest.raises(ValueError, match="fields"):
        decode_outcome(raw)
