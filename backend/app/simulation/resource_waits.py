"""Authoritative derived tote waits; no runtime/journal mutation (ADR0023)."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Literal

from app.contracts.scenario import Order
from app.simulation.recorder import ActorState, Event

if TYPE_CHECKING:
    from app.simulation.engine import Engine

_EVENTS = frozenset(
    {
        "order_arrived",
        "order_assigned",
        "order_rejected_inventory",
        "order_packed",
        "stock_reserved",
    }
)


@dataclass(frozen=True, slots=True)
class ResourceWait:
    actor_id: str
    start_tick: int
    end_tick: int
    reason: Literal["tote_unavailable"] = "tote_unavailable"
    open_ended: bool = False


def _events(engine: Engine, cutoff: int) -> dict[int, list[Event]]:
    result: dict[int, list[Event]] = defaultdict(list)
    for event in engine.ctx.recorder.events:
        if event.at_tick <= cutoff and event.kind in _EVENTS:
            result[event.at_tick].append(event)
    return result


def _busy_changes(engine: Engine, cutoff: int, pickers: set[str]) -> dict[int, Counter[str]]:
    changes: dict[int, Counter[str]] = defaultdict(Counter)
    for action in engine.ctx.recorder.actions:
        if action.actor_id not in pickers or action.state is ActorState.IDLE:
            continue
        if action.start_tick <= cutoff and action.end_tick > 0:
            changes[max(0, action.start_tick)][action.actor_id] += 1
            if action.end_tick <= cutoff:
                changes[action.end_tick][action.actor_id] -= 1
    for job in engine.picking.jobs.values():
        actor = job.picker.actor_id
        start = engine.ctx.recorder.last_end(actor)
        if start <= cutoff:
            changes[max(0, start)][actor] += 1
    return changes


def _advance(
    events: Iterable[Event], queued: dict[str, None], stock: dict[str, int], free: int
) -> int:
    for event in events:
        if event.kind == "order_arrived":
            queued[event.entity_id] = None
        elif event.kind == "order_assigned":
            queued.pop(event.entity_id, None)
            free -= 1
        elif event.kind == "order_rejected_inventory":
            queued.pop(event.entity_id, None)
        elif event.kind == "order_packed":
            free += 1
        elif event.kind == "stock_reserved":
            stock[event.payload["sku_id"]] -= event.payload["quantity"]
    return free


def _admissible_count(
    queued: Iterable[str], orders: Mapping[str, Order], stock: dict[str, int], limit: int
) -> int:
    available, count = stock.copy(), 0
    for identifier in queued:
        if count == limit:
            break
        lines = orders[identifier].lines
        if any(available.get(line.sku_id, 0) < line.quantity for line in lines):
            continue
        for line in lines:
            available[line.sku_id] -= line.quantity
        count += 1
    return count


def _append(
    result: list[ResourceWait],
    latest: dict[str, int],
    actors: list[str],
    now: int,
    end: int,
    *,
    open_ended: bool,
) -> None:
    for actor in actors:
        previous = latest.get(actor)
        if previous is not None and result[previous].end_tick == now:
            result[previous] = replace(result[previous], end_tick=end, open_ended=open_ended)
        else:
            latest[actor] = len(result)
            result.append(ResourceWait(actor, now, end, open_ended=open_ended))


def derive_resource_waits(engine: Engine, cutoff: int) -> tuple[ResourceWait, ...]:
    """Derive settled intervals through cutoff; a new boundary wait has zero elapsed ticks."""
    if cutoff < 0:
        raise ValueError("resource wait cutoff must be non-negative")
    inputs = engine.ctx.inputs
    pickers = {actor.actor_id for actor in inputs.actors.by_role("picker")}
    events, changes = _events(engine, cutoff), _busy_changes(engine, cutoff, pickers)
    stock = {
        lot.sku_id: lot.quantity
        for lot in inputs.assignment.initial_lots
        if inputs.assignment.active_assignment.get(lot.slot_id) == lot.sku_id
    }
    orders = {order.order_id: order for order in inputs.scenario.orders}
    times = sorted({0, cutoff, *events, *changes})
    queued: dict[str, None] = {}
    busy: Counter[str] = Counter()
    free = inputs.config.totes_total
    result: list[ResourceWait] = []
    latest: dict[str, int] = {}
    for index, now in enumerate(times):
        free = _advance(events.get(now, ()), queued, stock, free)
        busy.update(changes.get(now, {}))
        if free > 0 or not queued:
            continue
        idle = sorted(actor for actor in pickers if busy[actor] == 0)
        count = _admissible_count(queued, orders, stock, len(idle))
        until = times[index + 1] if now < cutoff else now
        _append(result, latest, idle[:count], now, until, open_ended=now == cutoff)
    return tuple(sorted(result, key=lambda wait: (wait.start_tick, wait.actor_id)))
