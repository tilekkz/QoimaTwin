"""Strict, versioned calendar choices with no inherited V2 hourly-rate defaults."""

from typing import Any, cast

from app.v3.coordinator_calendar_models import CalendarKind, CalendarLane, CoordinatorCalendar
from app.v3.workload_policy import fields

SCHEMA_ID = "qoima.coordinator-calendar.v3-proposal"
SCHEMA_VERSION = "0.1.0"
KINDS = ("unit_order", "receipt", "whole_order")


def _tick(value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("CALENDAR_EXACT_NONNEGATIVE_TICK_REQUIRED")
    return value


def _text(value: object) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError("CALENDAR_NONEMPTY_TEXT_REQUIRED")
    return value


def validate_calendar(value: CoordinatorCalendar) -> None:
    if type(value) is not CoordinatorCalendar or type(value.lanes) is not tuple:
        raise ValueError("CALENDAR_EXACT_IMMUTABLE_TYPE_REQUIRED")
    horizon, end = _tick(value.horizon_tick), _tick(value.end_tick)
    if not 0 < horizon <= end:
        raise ValueError("CALENDAR_REQUIRES_POSITIVE_H_AND_END_AT_OR_AFTER_H")
    _text(value.provenance)
    names: set[str] = set()
    for lane in value.lanes:
        _lane(lane, horizon)
        if lane.lane_id in names:
            raise ValueError("CALENDAR_DUPLICATE_LANE")
        names.add(lane.lane_id)


def _kind(value: object) -> None:
    if type(value) is not str or value not in KINDS:
        raise ValueError("CALENDAR_UNKNOWN_JOB_KIND")


def _lane(lane: CalendarLane, horizon: int) -> None:
    if type(lane) is not CalendarLane:
        raise ValueError("CALENDAR_EXACT_LANE_TYPE_REQUIRED")
    _text(lane.lane_id)
    _kind(lane.kind)
    if type(lane.job_ids) is not tuple or not lane.job_ids:
        raise ValueError("CALENDAR_NONEMPTY_IMMUTABLE_JOB_SEQUENCE_REQUIRED")
    if len({_text(job) for job in lane.job_ids}) != len(lane.job_ids):
        raise ValueError("CALENDAR_DUPLICATE_JOB_IN_LANE")
    if not _tick(lane.start_tick) < _tick(lane.end_tick) <= horizon:
        raise ValueError("CALENDAR_WINDOW_MUST_BE_WITHIN_H")


def calendar_document(value: CoordinatorCalendar) -> dict[str, Any]:
    validate_calendar(value)
    return {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "horizon_tick": value.horizon_tick,
        "end_tick": value.end_tick,
        "provenance": value.provenance,
        "lanes": [
            {
                "lane_id": lane.lane_id,
                "kind": lane.kind,
                "job_ids": list(lane.job_ids),
                "start_tick": lane.start_tick,
                "end_tick": lane.end_tick,
            }
            for lane in sorted(value.lanes, key=lambda item: item.lane_id)
        ],
    }


def _parse_lane(value: object) -> CalendarLane:
    row = fields(value, {"lane_id", "kind", "job_ids", "start_tick", "end_tick"})
    if type(row["job_ids"]) is not list:
        raise ValueError("CALENDAR_JOB_IDS_REQUIRE_JSON_ARRAY")
    return CalendarLane(
        _text(row["lane_id"]),
        cast(CalendarKind, _text(row["kind"])),
        tuple(_text(job) for job in row["job_ids"]),
        _tick(row["start_tick"]),
        _tick(row["end_tick"]),
    )


def parse_calendar(value: object) -> CoordinatorCalendar:
    row = fields(
        value, {"schema_id", "schema_version", "horizon_tick", "end_tick", "provenance", "lanes"}
    )
    if row["schema_id"] != SCHEMA_ID or row["schema_version"] != SCHEMA_VERSION:
        raise ValueError("CALENDAR_UNSUPPORTED_SCHEMA")
    if type(row["lanes"]) is not list:
        raise ValueError("CALENDAR_LANES_REQUIRE_JSON_ARRAY")
    result = CoordinatorCalendar(
        _tick(row["horizon_tick"]),
        _tick(row["end_tick"]),
        _text(row["provenance"]),
        tuple(sorted((_parse_lane(lane) for lane in row["lanes"]), key=lambda lane: lane.lane_id)),
    )
    validate_calendar(result)
    return result
