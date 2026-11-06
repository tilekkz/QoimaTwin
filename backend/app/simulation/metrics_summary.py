"""Export-ready KPI projection; no mutation of runtime or its journal."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import TYPE_CHECKING

from app.simulation.receiving import InboundState

if TYPE_CHECKING:
    from app.simulation.engine import Engine, RunOutcome


def queues(engine: Engine) -> dict[str, int]:
    result = {
        "orders": len(engine.picking.queue),
        "shipping": len(engine.shipping.buffer),
        "outbound": len(engine.outbound.tasks),
        "receiving_external": len(engine.receiving.external),
        "receiving": sum(p.state is InboundState.WAITING for p in engine.receiving.area),
        "putaway": sum(p.state is InboundState.PROCESSED for p in engine.receiving.area),
    }
    result.update({f"pack:{s.pack_id}": len(s.waiting) for s in engine.packing.stations.values()})
    return result


def utilization(engine: Engine, cutoff: int) -> dict[str, dict[str, float | None]]:
    actors = {a.actor_id: a.role for a in engine.ctx.inputs.actors.actors}
    counts = Counter(actors.values())
    totals: dict[str, Counter[str]] = defaultdict(Counter)
    for action in engine.ctx.recorder.actions:
        duration = max(0, min(action.end_tick, cutoff) - max(0, action.start_tick))
        totals[actors[action.actor_id]][action.state.value] += duration
    for actor, start in open_blocks(engine):
        totals[actors[actor]]["BLOCKED"] += max(0, cutoff - start)
    result: dict[str, dict[str, float | None]] = {}
    for role, count in counts.items():
        states = totals[role]
        active = states["TRAVEL"] + states["BUSY_SERVICE"]
        result[role] = {
            "active": active / (count * cutoff) if cutoff else None,
            "blocked": states["BLOCKED"] / (count * cutoff) if cutoff else None,
            "wait_resource": states["WAIT_RESOURCE"] / (count * cutoff) if cutoff else None,
        }
    return result


def open_blocks(engine: Engine) -> list[tuple[str, int]]:
    result = [
        (s.packer_id, s.blocked_since)
        for s in engine.packing.stations.values()
        if s.blocked_parcel is not None
    ]
    for job in engine.picking.jobs.values():
        start = engine.ctx.recorder.last_end(job.picker.actor_id)
        result.append((job.picker.actor_id, start))
    return result


def queue_means(engine: Engine, cutoff: int) -> dict[str, float | None]:
    areas: Counter[str] = Counter()
    samples = engine.metrics.queue_samples
    for index, (tick, sizes) in enumerate(samples):
        end = samples[index + 1][0] if index + 1 < len(samples) else cutoff
        width = max(0, min(end, cutoff) - tick)
        for name, size in sizes.items():
            areas[name] += size * width
    names = queues(engine)
    return {name: areas[name] / cutoff if cutoff else None for name in names}


def summary(engine: Engine, outcome: RunOutcome) -> dict[str, object]:
    tps = engine.ctx.grid.ticks_per_second
    windows = {}
    for name, cutoff, inclusive in [
        ("at_horizon", outcome.horizon_tick, False),
        ("at_end", outcome.end_tick, True),
    ]:
        window = engine.metrics.order_summary(cutoff, tps, inclusive=inclusive)
        window["utilization_by_role"] = utilization(engine, cutoff)
        window["queue_mean"] = queue_means(engine, cutoff)
        windows[name] = window
    return {
        **windows,
        "backlog_at_horizon": windows["at_horizon"]["backlog"],
        "status": outcome.status.value,
        "termination_reason": outcome.termination.value,
    }
