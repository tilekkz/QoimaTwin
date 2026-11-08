"""Business cycles exclude paid return; common actor work is summed once across all jobs."""

from fractions import Fraction

from app.v3.flow_profile_wire import record
from app.v3.interface import Json
from app.v3.receipt_run_validation import receipt_counts


def _cycles(values: list[int]) -> Json:
    if not values:
        return {"samples": 0, "mean_ticks": None, "p95_ticks": None}
    ordered = sorted(values)
    index = Fraction(95, 100) * (len(values) - 1)
    lo = index.numerator // index.denominator
    hi = min(lo + 1, len(values) - 1)
    return {
        "samples": len(values),
        "mean_ticks": record(Fraction(sum(values), len(values))),
        "p95_ticks": record(ordered[lo] + (index - lo) * (ordered[hi] - ordered[lo])),
    }


def _business(rows: list[Json], offered: dict[str, Json], key: str, sizes: dict[str, int]) -> Json:
    completed = [r for r in rows if r["shipped_tick"] is not None]
    arrived = sum(r["status"] != "unreleased" for r in rows)
    return {
        "arrived_orders": arrived,
        "completed_orders": len(completed),
        "backlog_orders": arrived - len(completed),
        "completed_units": sum(sizes[r[key]] for r in completed),
        "cycle": _cycles([r["shipped_tick"] - offered[r[key]]["arrival_tick"] for r in completed]),
    }


def window(point: Json, catalog: Json) -> Json:
    state = point["state"]
    unit_specs = {o["order_id"]: o for o in catalog["orders"]}
    whole_specs = {o["job_id"]: o for o in catalog["whole_process"]["orders"]}
    tokens = [
        *catalog["initial_units"],
        *(u for r in catalog["declared_receipts"] for u in r["units"]),
    ]
    whole_sizes = {
        k: sum(u["origin_hu"] == o["hu_id"] for u in tokens) for k, o in whole_specs.items()
    }
    whole = _business(state["whole_orders"], whole_specs, "job_id", whole_sizes)
    whole["pending_return"] = sum(
        r["admitted_tick"] is not None and r["returned_tick"] is None for r in state["whole_orders"]
    )
    whole["ports"] = _ports(state["whole_orders"], whole_specs, tokens)
    workers = [
        {k: w[k] for k in ("actor_id", "paid_ticks", "queue_ticks")} for w in state["workers"]
    ]
    paid, waiting = (sum(w[k] for w in workers) for k in ("paid_ticks", "queue_ticks"))
    return {
        "tick": point["tick"],
        "unit": _business(
            state["orders"],
            unit_specs,
            "order_id",
            {k: len(o["package_placements"]) for k, o in unit_specs.items()},
        ),
        "whole": whole,
        "receipts": receipt_counts(point, catalog),
        "labor": {
            "paid_ticks": paid,
            "assigned_wait_ticks": waiting,
            "assigned_exposure_ticks": paid + waiting,
            "actors": workers,
        },
    }


def _ports(rows: list[Json], offered: dict[str, Json], units: list[Json]) -> list[Json]:
    classes = {u["origin_hu"]: u["recipe"]["archetype_id"] for u in units}
    totals: dict[tuple[str, str], list[int]] = {}
    for row in rows:
        order = offered[row["job_id"]]
        key = order["port_id"], classes[order["hu_id"]]
        values = totals.setdefault(key, [0, 0])
        values[0] += row["port_reservation_ticks"]
        values[1] += row["port_service_ticks"]
    return [
        {"port_id": p, "archetype_id": c, "reservation_ticks": v[0], "service_ticks": v[1]}
        for (p, c), v in sorted(totals.items())
    ]


def summary(run: Json) -> Json:
    return {
        "metrics_version": "qoima-whole-flow-metrics-v1",
        "counts_boundary": "settled_tick_inclusive",
        "integral_window": "[0,T)",
        **{key: window(run[key], run["catalog"]) for key in ("at_horizon", "at_end")},
    }
