"""Selected aggregate KPIs only; no actor/SKU data, queues, notes or arbitrary nested fields."""

from __future__ import annotations

from collections.abc import Mapping

from app.explanations.errors import ExplanationError
from app.explanations.models import Fact
from app.explanations.validation import mapping, number

COUNTS = (
    "arrived_total",
    "packed_total",
    "dispatched_total",
    "unfulfilled_inventory_total",
    "backlog",
)
SCALARS = (
    "completion_rate",
    "backlog_max_age_s",
    "all_orders_makespan_s",
    "last_dispatch_s",
)


def metric_facts(side: Mapping[str, object], prefix: str) -> list[Fact]:
    result: list[Fact] = []
    if "metrics" not in side:
        return result
    metrics = mapping(side["metrics"])
    for window in ("at_horizon", "at_end"):
        if window not in metrics:
            continue
        data = mapping(metrics[window])
        path = f"{prefix}.metrics.{window}."
        for name in COUNTS + SCALARS:
            if name not in data:
                continue
            if name in COUNTS and type(data[name]) is not int:
                raise ExplanationError("invalid_facts")
            result.append(
                Fact(fact_id=path + name, value=None)
                if data[name] is None
                else number(data, name, path)
            )
        for name in ("cycle", "packed_cycle", "backlog_age"):
            if name not in data:
                continue
            distribution = mapping(data[name])
            for stat in ("mean_s", "p95_s"):
                if stat not in distribution:
                    raise ExplanationError("invalid_facts")
                result.append(
                    Fact(fact_id=f"{path}{name}.{stat}", value=None)
                    if distribution[stat] is None
                    else number(distribution, stat, f"{path}{name}.")
                )
    return result
