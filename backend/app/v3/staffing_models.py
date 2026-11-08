"""Explicit analytical cover periods, never admitted tasks or measured travel durations."""

from dataclasses import dataclass

from app.v3.staff_registry_values import Role, period, role, text, tick


@dataclass(frozen=True, slots=True)
class AnalyticalCover:
    cover_id: str
    actor_id: str
    station_id: str
    start_tick: int
    end_tick: int
    outward_ticks: int
    return_ticks: int

    def __post_init__(self) -> None:
        for value in (self.cover_id, self.actor_id, self.station_id):
            text(value)
        period(self.start_tick, self.end_tick)
        if tick(self.outward_ticks) == 0 or tick(self.return_ticks) == 0:
            raise ValueError("POSITIVE_ANALYTICAL_TRANSITION_REQUIRED")
        if self.outward_ticks + self.return_ticks >= self.end_tick - self.start_tick:
            raise ValueError("EMPTY_ANALYTICAL_COVER_WINDOW")


@dataclass(frozen=True, slots=True)
class StaffingExposure:
    start_tick: int
    end_tick: int
    role_ticks: tuple[tuple[Role, int], ...]
    transition_person_ticks: int
    unavailable_person_ticks: int
    roster_person_ticks: int

    def role_person_ticks(self, requested_role: Role) -> int:
        return dict(self.role_ticks)[role(requested_role)]

    @property
    def operational_admission(self) -> bool:
        return False

    @property
    def full_n4_pass(self) -> bool:
        return False
