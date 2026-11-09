"""Strict calendar wire roundtrips and source admission remain separate authorities."""

from copy import deepcopy
from typing import Any

import pytest

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.coordinator_calendar import compile_calendar_profile, materialize_calendar
from app.v3.coordinator_calendar_io import calendar_document, parse_calendar
from app.v3.coordinator_calendar_models import CalendarLane, CoordinatorCalendar
from app.v3.coordinator_profile import load_coordinator_inputs
from tests.v3.test_coordinator_calendar import calendar
from tests.v3.test_coordinator_profile_fixtures import (
    coordinator_document,
    coordinator_sources,
)

__all__ = ["coordinator_sources"]


def test_wire_is_exact_and_canonical_without_invented_defaults() -> None:
    document = calendar_document(calendar())
    assert parse_calendar(document) == calendar()
    assert parse_calendar(parse_json(canonical_bytes(document))) == calendar()
    for key in document:
        changed = deepcopy(document)
        del changed[key]
        with pytest.raises(ValueError):
            parse_calendar(changed)
    with pytest.raises(ValueError):
        parse_calendar({**document, "rate_per_hour": 240})


@pytest.mark.parametrize("invalid", [True, 0.0, -1, "0"])
def test_wire_rejects_alias_clocks(invalid: Any) -> None:
    document = calendar_document(calendar())
    document["lanes"][0]["start_tick"] = invalid
    with pytest.raises(ValueError):
        parse_calendar(document)


def test_declared_one_hour_and_eight_hour_change_only_arrivals_and_horizons() -> None:
    source = coordinator_document()
    for horizon, middle in ((3_600_000_000, 1_800_000_000), (28_800_000_000, 14_400_000_000)):
        plan = CoordinatorCalendar(
            horizon,
            horizon + 900_000_000,
            "Two existing unit orders, explicit sparse subset; not normal/peak acceptance",
            (CalendarLane("unit", "unit_order", ("O1", "O2"), 0, horizon),),
        )
        result = parse_json(materialize_calendar(source, plan).choices_bytes)
        assert [row["arrival_tick"] for row in result["orders"]] == [0, middle]
        assert result["orders"][0]["source_hu"] == source["orders"][0]["source_hu"]
        assert result["materials"] == source["materials"]
        assert result["registry"] == source["registry"]


def test_source_compilation_is_required_after_clock_materialization(
    coordinator_sources: Any,
) -> None:
    bundle, conveyor = coordinator_sources
    source = coordinator_document()
    plan = CoordinatorCalendar(
        3_600_000_000,
        4_500_000_000,
        "Explicit two-order source subset",
        (CalendarLane("unit", "unit_order", ("O1", "O2"), 0, 3_600_000_000),),
    )
    result = compile_calendar_profile(bundle, conveyor, source, plan)
    reread = load_coordinator_inputs(result.frozen_bytes)
    assert reread.input_hash == result.input_hash
    assert reread.profile.world.receipts.flow.stock == result.profile.world.receipts.flow.stock


def test_materializing_clocks_does_not_grant_invalid_resource_authority(
    coordinator_sources: Any,
) -> None:
    bundle, conveyor = coordinator_sources
    source = coordinator_document()
    source["unit_assignments"][0]["cart_id"] = "missing-cart"
    plan = CoordinatorCalendar(
        900_000_000,
        1_800_000_000,
        "Invalid resource is never repaired",
        (CalendarLane("unit", "unit_order", ("O1", "O2"), 0, 900_000_000),),
    )
    assert materialize_calendar(source, plan).operational_admission is False
    with pytest.raises(ValueError):
        compile_calendar_profile(bundle, conveyor, source, plan)
