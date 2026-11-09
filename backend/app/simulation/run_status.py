"""Subsystem completion and ordered reasons (ADR 0009 A05, ADR 0013)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from app.simulation.engine import Engine

type SubsystemState = Literal["complete", "partial", "blocked", "incomplete"]


class RunStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


class Termination(StrEnum):
    DRAINED = "drained"
    UNFULFILLED_INVENTORY = "unfulfilled_inventory"
    MAX_DRAIN = "max_drain"
    DEADLOCK = "deadlock"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class SubsystemStatus:
    status: SubsystemState
    arrived_total: int
    completed_total: int
    pending_total: int
    rejected_total: int = 0
    blocked_since_tick: int | None = None


@dataclass(frozen=True, slots=True)
class RunOutcome:
    status: RunStatus
    termination: Termination
    horizon_tick: int
    end_tick: int
    termination_reasons: tuple[Termination, ...] = ()
    subsystems: dict[str, SubsystemStatus] = field(default_factory=dict)
    error_type: str | None = None
    error_message: str | None = None


def classify_outcome(
    engine: Engine, horizon: int, deadline: int, error: Exception | None = None
) -> RunOutcome:
    counts = engine.metrics.counts()
    rejected = counts["unfulfilled_inventory_total"]
    unresolved = counts["arrived_total"] - counts["dispatched_total"] - rejected
    pending = bool(engine.ctx.sched.pending_count())
    inbound_left = engine.receiving.arrived_total - len(engine.receiving.putaway_ticks)
    deadlock = engine.receiving.blocked() or (unresolved + inbound_left > 0 and not pending)
    reasons = tuple(
        reason
        for reason, applies in (
            (Termination.ERROR, error is not None),
            (Termination.DEADLOCK, deadlock),
            (Termination.MAX_DRAIN, pending and error is None),
            (Termination.UNFULFILLED_INVENTORY, rejected > 0),
        )
        if applies
    ) or (Termination.DRAINED,)
    status = RunStatus.COMPLETE if reasons == (Termination.DRAINED,) else RunStatus.PARTIAL
    end = deadline if pending and error is None else engine.ctx.now
    return RunOutcome(
        RunStatus.FAILED if error else status,
        reasons[0],
        horizon,
        end,
        reasons,
        _subsystems(engine, unresolved, pending),
        type(error).__name__ if error else None,
        str(error) if error else None,
    )


def _subsystems(engine: Engine, unresolved: int, pending: bool) -> dict[str, SubsystemStatus]:
    counts, receiving = engine.metrics.counts(), engine.receiving
    orders: SubsystemState = "partial" if counts["unfulfilled_inventory_total"] else "complete"
    if unresolved:
        orders = "incomplete" if pending else "blocked"
    remaining = receiving.arrived_total - len(receiving.putaway_ticks)
    inbound: SubsystemState = (
        "blocked"
        if receiving.blocked() or (remaining and not pending)
        else "incomplete"
        if remaining
        else "complete"
    )
    starts = [receiving.putaway_blocked_since_tick, receiving.external_blocked_since_tick]
    blocked_since = min((tick for tick in starts if tick is not None), default=None)
    return {
        "orders": SubsystemStatus(
            orders,
            counts["arrived_total"],
            counts["dispatched_total"],
            unresolved,
            counts["unfulfilled_inventory_total"],
        ),
        "receiving": SubsystemStatus(
            inbound,
            receiving.arrived_total,
            len(receiving.putaway_ticks),
            remaining,
            blocked_since_tick=blocked_since,
        ),
    }
