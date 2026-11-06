"""Minimal v2 counters; the detailed window metrics are published separately."""

from typing import Any

from app.simulation.engine import Engine, RunOutcome


def project_metrics(engine: Engine, outcome: RunOutcome) -> dict[str, Any]:
    orders = list(engine.metrics.orders.values())
    tps = engine.ctx.grid.ticks_per_second
    cycles = sorted((r.dispatched - r.arrival) / tps for r in orders if r.dispatched is not None)
    horizon = outcome.horizon_tick
    backlog = sum(
        r.arrival < horizon and (r.dispatched is None or r.dispatched >= horizon) for r in orders
    )
    index = (len(cycles) - 1) * 0.95
    lower = int(index)
    p95 = (
        (
            cycles[lower]
            + (cycles[min(lower + 1, len(cycles) - 1)] - cycles[lower]) * (index - lower)
        )
        if cycles
        else None
    )
    last = max((r.dispatched for r in orders if r.dispatched is not None), default=None)
    return {
        **engine.metrics.counts(),
        "backlog_at_horizon": backlog,
        "all_orders_makespan_s": last / tps
        if last is not None and len(cycles) == len(orders)
        else None,
        "mean_cycle_s": sum(cycles) / len(cycles) if cycles else None,
        "p95_cycle_s": p95,
        "role_metrics": {},
        "queue_metrics": {},
        "conveyor_metrics": {},
        "inventory_balance": {
            sku: {str(kind): qty for kind, qty in engine.ctx.ledger.buckets(sku).items()}
            for sku in engine.ctx.ledger.skus()
        },
    }
