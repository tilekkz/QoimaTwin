"""Materialize arrival clocks while preserving the exact declared finite job population."""

from copy import deepcopy
from hashlib import sha256
from typing import Any

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.conveyor_models import ConveyorSource
from app.v3.coordinator_calendar_io import calendar_document, validate_calendar
from app.v3.coordinator_calendar_models import (
    CalendarKind,
    CoordinatorCalendar,
    MaterializedCalendar,
)
from app.v3.coordinator_profile import CompiledCoordinatorProfile, compile_coordinator_profile
from app.v3.coordinator_profile_schema import validate_document
from app.v3.input_models import V3Bundle

TABLES: tuple[tuple[CalendarKind, str, str], ...] = (
    ("unit_order", "orders", "order_id"),
    ("receipt", "receipts", "receipt_id"),
    ("whole_order", "whole_orders", "job_id"),
)


def _jobs(value: dict[str, Any]) -> dict[str, tuple[CalendarKind, dict[str, Any]]]:
    jobs: dict[str, tuple[CalendarKind, dict[str, Any]]] = {}
    for kind, table, field in TABLES:
        for row in value[table]:
            key = row[field]
            if key in jobs:
                raise ValueError("CALENDAR_DUPLICATE_GLOBAL_JOB_ID")
            jobs[key] = kind, row
    return jobs


def _arrivals(value: dict[str, Any], calendar: CoordinatorCalendar) -> None:
    jobs = _jobs(value)
    assigned: set[str] = set()
    for lane in calendar.lanes:
        width, count = lane.end_tick - lane.start_tick, len(lane.job_ids)
        for index, key in enumerate(lane.job_ids):
            if key not in jobs or jobs[key][0] != lane.kind:
                raise ValueError("CALENDAR_UNKNOWN_JOB_OR_WRONG_KIND")
            if key in assigned:
                raise ValueError("CALENDAR_JOB_ASSIGNED_MORE_THAN_ONCE")
            assigned.add(key)
            jobs[key][1]["arrival_tick"] = lane.start_tick + index * width // count
    if assigned != jobs.keys():
        raise ValueError("CALENDAR_MUST_COVER_EVERY_EXISTING_JOB")


def _offered(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "scope": "explicit_coordinator_job_population_only",
        "source": value["source"],
        "horizon_tick": value["horizon_tick"],
        "end_tick": value["end_tick"],
        "jobs": {
            kind: sorted(value[table], key=lambda row: row[field]) for kind, table, field in TABLES
        },
    }


def materialize_calendar(
    document: Any,
    calendar: CoordinatorCalendar,
) -> MaterializedCalendar:
    """Shape-valid choices are not physical/source admission; compile before any run."""
    validate_document(document)
    validate_calendar(calendar)
    value = deepcopy(document)
    value["horizon_tick"], value["end_tick"] = calendar.horizon_tick, calendar.end_tick
    _arrivals(value, calendar)
    return MaterializedCalendar(
        canonical_bytes(value),
        canonical_bytes(calendar_document(calendar)),
        sha256(canonical_bytes(_offered(value))).hexdigest(),
        tuple((kind, len(value[table])) for kind, table, _ in TABLES),
    )


def compile_calendar_profile(
    bundle: V3Bundle,
    conveyor: ConveyorSource,
    document: Any,
    calendar: CoordinatorCalendar,
) -> CompiledCoordinatorProfile:
    """Re-enter full raw source, resource, role and stock authority after changing clocks."""
    materialized = materialize_calendar(document, calendar)
    return compile_coordinator_profile(bundle, conveyor, parse_json(materialized.choices_bytes))
