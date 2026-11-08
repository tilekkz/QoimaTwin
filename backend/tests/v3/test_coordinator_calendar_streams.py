"""Different stream calendars preserve exactly declared identities and cargo."""

from copy import deepcopy

import pytest

from app.storage.canonical_json import parse_json
from app.v3.coordinator_calendar import materialize_calendar
from app.v3.coordinator_calendar_models import CalendarLane, CoordinatorCalendar
from tests.v3.test_coordinator_profile_fixtures import coordinator_document, with_whole_receipt


def test_three_streams_keep_independent_half_open_clocks_and_exact_population() -> None:
    value = with_whole_receipt(coordinator_document())
    before = deepcopy(value)
    receipt_id = value["receipts"][0]["receipt_id"]
    whole_id = value["whole_orders"][0]["job_id"]
    assert len(value["receipts"]) == len(value["whole_orders"]) == 1
    plan = CoordinatorCalendar(
        100,
        200,
        "Hand mixed-stream clocks",
        (
            CalendarLane("u", "unit_order", ("O1", "O2"), 20, 100),
            CalendarLane("r", "receipt", (receipt_id,), 10, 30),
            CalendarLane("w", "whole_order", (whole_id,), 90, 100),
        ),
    )
    result = materialize_calendar(value, plan)
    actual = parse_json(result.choices_bytes)
    assert result.counts == (("unit_order", 2), ("receipt", 1), ("whole_order", 1))
    assert [row["arrival_tick"] for row in actual["orders"]] == [20, 60]
    assert actual["receipts"][0]["arrival_tick"] == 10
    assert actual["whole_orders"][0]["arrival_tick"] == 90
    for key in ("orders", "receipts", "whole_orders"):
        for expected, observed in zip(before[key], actual[key], strict=True):
            expected["arrival_tick"] = observed["arrival_tick"]
            assert expected == observed
    assert value == with_whole_receipt(coordinator_document())


def test_cross_stream_duplicate_identity_is_not_disambiguated_silently() -> None:
    value = with_whole_receipt(coordinator_document())
    value["receipts"][0]["receipt_id"] = "O1"
    with pytest.raises(ValueError, match="CALENDAR_DUPLICATE_GLOBAL_JOB_ID"):
        materialize_calendar(value, CoordinatorCalendar(100, 200, "No implicit rename", ()))
