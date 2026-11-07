"""Strict schemas for the business/resource observations from ADR 0034."""

from app.v3.interface import Json
from app.v3.run_schema import TICK, WAIT_REASONS, nullable, obj

NUMBER = {"type": "number", "minimum": 0}


def _business() -> Json:
    return obj(
        {
            **{
                key: TICK
                for key in ("arrived_hus", "completed_hus", "backlog_hus", "completed_units")
            },
            "completed_mass_kg": NUMBER,
            "mean_cycle_s": nullable(NUMBER),
            "p95_cycle_s": nullable(NUMBER),
        }
    )


def _map(values: Json, names: Json | None = None) -> Json:
    return {
        "type": "object",
        "additionalProperties": values,
        **({"propertyNames": names} if names else {}),
    }


def _window() -> Json:
    roles = {"receive": NUMBER, "ship": NUMBER}
    utilization = nullable({**NUMBER, "maximum": 1})
    queue = obj(
        {
            "job_seconds": NUMBER,
            "mean_jobs": nullable(NUMBER),
            "wait_seconds_by_reason": _map(NUMBER, {"enum": WAIT_REASONS}),
        }
    )
    return obj(
        {
            "tick": TICK,
            "time_s": NUMBER,
            "operational_status": {"enum": ["complete", "partial"]},
            "inbound": _business(),
            "outbound": _business(),
            "worker_busy_s": NUMBER,
            "worker_busy_s_by_actor": _map(NUMBER),
            "roster_utilization": utilization,
            "role_busy_s": obj(roles),
            "role_pool_utilization": obj({role: utilization for role in roles}),
            "queues": _map(queue),
        }
    )


def metrics_schema() -> Json:
    return obj(
        {
            "metrics_version": {"const": "qoima-manual-metrics-v1"},
            "counts_boundary": {"const": "settled_tick_inclusive"},
            "integral_window": {"const": "[0,T)"},
            "cycle_completion": {"const": "inbound_putaway_or_outbound_handover"},
            "at_horizon": _window(),
            "at_end": _window(),
        }
    )
