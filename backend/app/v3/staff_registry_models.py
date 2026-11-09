"""Immutable registry assumptions. These values never own a live worker or station."""

from dataclasses import dataclass
from fractions import Fraction

from app.v3.staff_registry_values import EQUIPMENT, Role, period, role, text, typed_tuple


@dataclass(frozen=True, slots=True)
class WorkerCapability:
    actor_id: str
    primary_role: Role
    eligible_roles: tuple[Role, ...]
    permitted_equipment: tuple[str, ...]

    def __post_init__(self) -> None:
        text(self.actor_id)
        role(self.primary_role)
        typed_tuple(self.eligible_roles, str)
        typed_tuple(self.permitted_equipment, str)
        for item in self.eligible_roles:
            role(item)
        for equipment in self.permitted_equipment:
            if text(equipment) not in EQUIPMENT:
                raise ValueError("UNKNOWN_STAFF_EQUIPMENT")
        if self.primary_role not in self.eligible_roles:
            raise ValueError("PRIMARY_SKILL_REQUIRED")
        if len(set(self.eligible_roles)) != len(self.eligible_roles) or len(
            set(self.permitted_equipment)
        ) != len(self.permitted_equipment):
            raise ValueError("DUPLICATE_STAFF_CAPABILITY")


@dataclass(frozen=True, slots=True)
class Unavailability:
    actor_id: str
    start_tick: int
    end_tick: int
    reason: str

    def __post_init__(self) -> None:
        text(self.actor_id)
        text(self.reason)
        period(self.start_tick, self.end_tick)


@dataclass(frozen=True, slots=True)
class StationBinding:
    station_id: str
    primary_actor_id: str

    def __post_init__(self) -> None:
        text(self.station_id)
        text(self.primary_actor_id)


@dataclass(frozen=True, slots=True)
class StaffStation:
    station_id: str
    service_node_id: str
    worker_position: tuple[Fraction, Fraction, Fraction]
    work_node_id: str
    work_position: tuple[Fraction, Fraction, Fraction]
    spur_resource_id: str


@dataclass(frozen=True, slots=True)
class StaffSource:
    revision: str
    fingerprints: tuple[tuple[str, str, int], ...]
    actor_ids: tuple[str, ...]
    primary_roles: tuple[tuple[str, Role], ...]
    receivers: tuple[str, ...]
    shippers: tuple[str, ...]
    forklift_pairs: tuple[tuple[str, str], ...]
    stations: tuple[StaffStation, ...]
