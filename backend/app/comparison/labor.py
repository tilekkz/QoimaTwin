"""Labor by actor and role in [0, cutoff) (01 §10, ADR 0011/0016).

Labor = TRAVEL + BUSY_SERVICE. BLOCKED (including still-open blocks) and WAIT_RESOURCE are
reported separately and never counted as labor. IDLE is ignored.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from fractions import Fraction

from app.contracts.base import FrozenModel
from app.simulation.recorder import Action, ActorState

_STATES = (
    ActorState.TRAVEL,
    ActorState.BUSY_SERVICE,
    ActorState.BLOCKED,
    ActorState.WAIT_RESOURCE,
)


class LaborEntry(FrozenModel):
    travel_s: float
    busy_service_s: float
    blocked_s: float
    wait_resource_s: float
    labor_s: float
    labor_ticks: int
    blocked_ticks: int
    wait_resource_ticks: int


class LaborSummary(FrozenModel):
    cutoff_tick: int
    cutoff_s: float
    by_actor: dict[str, LaborEntry]
    by_role: dict[str, LaborEntry]
    total_labor_s: float
    total_blocked_s: float
    total_wait_resource_s: float
    labor_ticks: int
    blocked_ticks: int
    wait_resource_ticks: int


def _entry(ticks: Mapping[ActorState, int], tps: int) -> LaborEntry:
    labor = ticks[ActorState.TRAVEL] + ticks[ActorState.BUSY_SERVICE]
    return LaborEntry(
        travel_s=float(Fraction(ticks[ActorState.TRAVEL], tps)),
        busy_service_s=float(Fraction(ticks[ActorState.BUSY_SERVICE], tps)),
        blocked_s=float(Fraction(ticks[ActorState.BLOCKED], tps)),
        wait_resource_s=float(Fraction(ticks[ActorState.WAIT_RESOURCE], tps)),
        labor_s=float(Fraction(labor, tps)),
        labor_ticks=labor,
        blocked_ticks=ticks[ActorState.BLOCKED],
        wait_resource_ticks=ticks[ActorState.WAIT_RESOURCE],
    )


def _actor_ticks(
    actions: Iterable[Action],
    roles: Mapping[str, str],
    open_blocks: Iterable[tuple[str, int]],
    cutoff: int,
) -> dict[str, dict[ActorState, int]]:
    ticks = {actor: dict.fromkeys(_STATES, 0) for actor in sorted(roles)}
    for action in actions:
        if action.state in _STATES and action.actor_id in ticks:
            clipped = min(action.end_tick, cutoff) - max(action.start_tick, 0)
            ticks[action.actor_id][action.state] += max(0, clipped)
    for actor, start in open_blocks:
        if actor in ticks:
            ticks[actor][ActorState.BLOCKED] += max(0, cutoff - max(start, 0))
    return ticks


def labor_breakdown(
    actions: Iterable[Action],
    roles: Mapping[str, str],
    *,
    open_blocks: Iterable[tuple[str, int]],
    cutoff_tick: int,
    tps: int,
) -> LaborSummary:
    """Exact per-actor and per-role totals; every roster actor appears, vehicles never."""
    per_actor = _actor_ticks(actions, roles, open_blocks, cutoff_tick)
    per_role: dict[str, dict[ActorState, int]] = defaultdict(lambda: dict.fromkeys(_STATES, 0))
    for actor, states in per_actor.items():
        for state, value in states.items():
            per_role[roles[actor]][state] += value
    totals = dict.fromkeys(_STATES, 0)
    for states in per_actor.values():
        for state, value in states.items():
            totals[state] += value
    labor = totals[ActorState.TRAVEL] + totals[ActorState.BUSY_SERVICE]
    return LaborSummary(
        cutoff_tick=cutoff_tick,
        cutoff_s=float(Fraction(cutoff_tick, tps)),
        by_actor={actor: _entry(states, tps) for actor, states in per_actor.items()},
        by_role={role: _entry(per_role[role], tps) for role in sorted(per_role)},
        total_labor_s=float(Fraction(labor, tps)),
        total_blocked_s=float(Fraction(totals[ActorState.BLOCKED], tps)),
        total_wait_resource_s=float(Fraction(totals[ActorState.WAIT_RESOURCE], tps)),
        labor_ticks=labor,
        blocked_ticks=totals[ActorState.BLOCKED],
        wait_resource_ticks=totals[ActorState.WAIT_RESOURCE],
    )
