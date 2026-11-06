"""Event and action journal of one run (contracts/run.schema.json, ADR 0003).

Events get a global `seq` when emitted. Actions are half-open `[start, end)` intervals per actor
and must not overlap; TRAVEL carries waypoints, every other state carries a fixed position.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.simulation.scheduler import Phase

Vec3 = tuple[float, float, float]


class ActorState(StrEnum):
    TRAVEL = "TRAVEL"
    BUSY_SERVICE = "BUSY_SERVICE"
    BLOCKED = "BLOCKED"
    WAIT_RESOURCE = "WAIT_RESOURCE"
    IDLE = "IDLE"


class RecorderError(RuntimeError):
    """An action or event violates journal invariants."""


@dataclass(frozen=True, slots=True)
class Event:
    seq: int
    at_tick: int
    phase: Phase
    kind: str
    entity_id: str
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class Waypoint:
    node_id: str
    pos: Vec3
    at_tick: int


@dataclass(frozen=True, slots=True)
class Action:
    action_id: str
    actor_id: str
    state: ActorState
    operation: str
    start_tick: int
    end_tick: int
    entity_id: str | None
    pos: Vec3 | None = None
    waypoints: tuple[Waypoint, ...] = ()


@dataclass(slots=True)
class Recorder:
    events: list[Event] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    _last_end: dict[str, int] = field(default_factory=dict)
    _last_key: tuple[int, int] = (-1, -1)

    def emit(self, at_tick: int, phase: Phase, kind: str, entity_id: str, **payload: Any) -> Event:
        key = (at_tick, int(phase))
        if key < self._last_key:
            raise RecorderError(f"event {kind} at {key} is earlier than {self._last_key}")
        self._last_key = key
        event = Event(len(self.events), at_tick, phase, kind, entity_id, payload)
        self.events.append(event)
        return event

    def act(
        self,
        actor_id: str,
        state: ActorState,
        operation: str,
        start_tick: int,
        end_tick: int,
        entity_id: str | None,
        *,
        pos: Vec3 | None = None,
        waypoints: tuple[Waypoint, ...] = (),
    ) -> Action:
        if end_tick <= start_tick:
            raise RecorderError(f"{actor_id} {operation}: empty interval [{start_tick},{end_tick})")
        if (state is ActorState.TRAVEL) != bool(waypoints) or (pos is None) == bool(waypoints):
            raise RecorderError(f"{actor_id} {operation}: TRAVEL needs waypoints, others need pos")
        if waypoints and (waypoints[0].at_tick != start_tick or waypoints[-1].at_tick != end_tick):
            raise RecorderError(f"{actor_id} {operation}: waypoints do not span the action")
        if start_tick < self._last_end.get(actor_id, 0):
            raise RecorderError(f"{actor_id} {operation}: overlaps previous action")
        self._last_end[actor_id] = end_tick
        action = Action(
            f"A{len(self.actions):07d}",
            actor_id,
            state,
            operation,
            start_tick,
            end_tick,
            entity_id,
            pos,
            waypoints,
        )
        self.actions.append(action)
        return action

    def of_kind(self, kind: str) -> list[Event]:
        return [e for e in self.events if e.kind == kind]
