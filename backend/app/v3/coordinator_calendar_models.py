"""Explicit clocks for a finite declared population, never implicit stock or demand."""

from dataclasses import dataclass
from typing import Literal

CalendarKind = Literal["unit_order", "receipt", "whole_order"]


@dataclass(frozen=True, slots=True)
class CalendarLane:
    lane_id: str
    kind: CalendarKind
    job_ids: tuple[str, ...]
    start_tick: int
    end_tick: int


@dataclass(frozen=True, slots=True)
class CoordinatorCalendar:
    horizon_tick: int
    end_tick: int
    provenance: str
    lanes: tuple[CalendarLane, ...]


@dataclass(frozen=True, slots=True)
class MaterializedCalendar:
    choices_bytes: bytes
    calendar_bytes: bytes
    offered_workload_hash: str
    counts: tuple[tuple[CalendarKind, int], ...]

    @property
    def operational_admission(self) -> Literal[False]:
        return False
