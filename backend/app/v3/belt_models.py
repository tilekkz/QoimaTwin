"""Explicit bounded conveyor jobs, microsecond observations and immutable journal."""

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from app.v3.conveyor_models import ConveyorPayload


@dataclass(frozen=True, slots=True)
class BeltJob:
    job_id: str
    hu_id: str
    payload: ConveyorPayload
    arrival_tick: int
    route: tuple[str, ...]
    station_id: str | None
    station_dwell_tick: int


@dataclass(frozen=True, slots=True)
class BeltPose:
    edge_id: str
    progress: Fraction
    yaw_quarters: Fraction


@dataclass(frozen=True, slots=True)
class BeltStep:
    phase: Literal["motion", "pivot", "station"]
    edge_id: str
    start: BeltPose
    end: BeltPose
    duration_tick: int
    resources: frozenset[str]
    guards: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class BeltMotion:
    phase: str
    start_tick: int
    planned_end_tick: int
    start: BeltPose
    end: BeltPose


@dataclass(frozen=True, slots=True)
class BeltCarrier:
    job_id: str
    hu_id: str
    payload_id: str
    status: str
    pose: BeltPose | None
    motion: BeltMotion | None
    occupied_cells: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BeltSnapshot:
    tick: int
    arrived: int
    completed: int
    carriers: tuple[BeltCarrier, ...]
    leases: tuple[tuple[str, str], ...]
    queue_ticks: int


@dataclass(frozen=True, slots=True)
class BeltEvent:
    seq: int
    tick: int
    kind: str
    job_id: str
    hu_id: str
    payload_id: str
    edge_id: str | None
    pose: BeltPose | None
    planned_end_tick: int | None
    resources: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BeltOutcome:
    status: Literal["complete", "partial"]
    events: tuple[BeltEvent, ...]
    at_horizon: BeltSnapshot
    at_end: BeltSnapshot
