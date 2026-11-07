"""Export-ready KPI projection; no mutation of runtime or its journal."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from typing import TYPE_CHECKING

from app.simulation.labor_metrics import (
    actor_ticks,
    blocking_summary,
    labor_by_role,
    picker_summary,
    station_summary,
)
from app.simulation.labor_metrics import open_blocks as open_blocks
from app.simulation.observations import inventory_balances
from app.simulation.observations import queues as queues
from app.simulation.resource_metrics import resource_summary

if TYPE_CHECKING:
    from app.simulation.engine import Engine, RunOutcome


def utilization(engine: Engine, cutoff: int) -> dict[str, dict[str, float | None]]:
    actors = {a.actor_id: a.role for a in engine.ctx.inputs.actors.actors}
    counts = Counter(actors.values())
    totals = {role: Counter[str]() for role in counts}
    for actor_id, states in actor_ticks(engine, cutoff).items():
        totals[actors[actor_id]].update(states)
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
        window = _window(engine, cutoff, inclusive=inclusive)
        inventory = inventory_balances(engine) if inclusive else engine.observer.horizon_inventory
        window["inventory_balance"] = {sku: dict(buckets) for sku, buckets in inventory.items()}
        windows[name] = window
    return {
        **windows,
        "backlog_at_horizon": windows["at_horizon"]["backlog"],
        "status": outcome.status.value,
        "termination_reason": outcome.termination.value,
        "termination_reasons": [reason.value for reason in outcome.termination_reasons],
        "subsystems": {
            name: {
                **asdict(status),
                "blocked_since_s": status.blocked_since_tick / tps
                if status.blocked_since_tick is not None
                else None,
            }
            for name, status in outcome.subsystems.items()
        },
        "receiving_limits": {
            "staging_reservations_full_since_s": _seconds(
                engine.receiving.staging_full_since_tick, tps
            ),
            "staging_physical_full_since_s": _seconds(
                engine.receiving.staging_physical_full_since_tick, tps
            ),
            "putaway_blocked_since_s": _seconds(engine.receiving.putaway_blocked_since_tick, tps),
            "external_blocked_since_s": _seconds(engine.receiving.external_blocked_since_tick, tps),
        },
        "error": {"type": outcome.error_type, "message": outcome.error_message}
        if outcome.error_type is not None
        else None,
    }


def _seconds(tick: int | None, tps: int) -> float | None:
    return tick / tps if tick is not None else None


def _window(engine: Engine, cutoff: int, *, inclusive: bool) -> dict[str, object]:
    window = engine.metrics.order_summary(
        cutoff, engine.ctx.grid.ticks_per_second, inclusive=inclusive
    )
    resources = resource_summary(engine, cutoff)
    counts = Counter(
        event.kind
        for event in engine.ctx.recorder.events
        if (event.at_tick <= cutoff if inclusive else event.at_tick < cutoff)
    )
    resources["receiving_metrics"].update(
        {
            "accepted_total": counts["receipt_accepted"],
            "processed_total": counts["receipt_processed"],
            "putaway_total": counts["pallet_putaway"],
        }
    )
    queue_mean = queue_means(engine, cutoff)
    window.update(resources)
    window["utilization_by_role"] = utilization(engine, cutoff)
    window["queue_mean"] = queue_mean
    window["picker_metrics"] = picker_summary(engine, cutoff)
    window["station_metrics"] = station_summary(engine, cutoff, queue_mean, inclusive=inclusive)
    labor = labor_by_role(engine, cutoff)
    window["labor_by_role"] = labor
    window["total_active_labor_s"] = sum(role["active_s"] for role in labor.values())
    window["blocking"] = blocking_summary(engine, cutoff)
    return window
