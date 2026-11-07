"""Schema-v2 KPIs: coherent horizon counts/cycles, utilization and waiting queues."""

from typing import Any, cast

from app.simulation.engine import Engine, RunOutcome
from app.simulation.metrics_summary import summary


def project_metrics(engine: Engine, outcome: RunOutcome) -> dict[str, Any]:
    windows = cast(dict[str, Any], summary(engine, outcome))
    horizon = windows["at_horizon"]
    return {
        **{key: horizon[key] for key in engine.metrics.counts()},
        "backlog_at_horizon": horizon["backlog"],
        "all_orders_makespan_s": horizon["all_orders_makespan_s"],
        "mean_cycle_s": horizon["cycle"]["mean_s"],
        "p95_cycle_s": horizon["cycle"]["p95_s"],
        "role_metrics": horizon["utilization_by_role"],
        "queue_metrics": horizon["queue_mean"],
        "conveyor_metrics": {},
        "inventory_balance": {
            sku: {str(kind): qty for kind, qty in engine.ctx.ledger.buckets(sku).items()}
            for sku in engine.ctx.ledger.skus()
        },
    }
