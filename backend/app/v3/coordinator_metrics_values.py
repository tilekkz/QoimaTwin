"""Exact observation arithmetic shared by the new coordinator metrics only."""

from fractions import Fraction

from app.v3.flow_profile_wire import record
from app.v3.interface import Json


def integer(value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("Coordinator metric requires a nonnegative exact integer")
    return value


def ratio(numerator: int, denominator: int) -> Json | None:
    return record(Fraction(numerator, denominator)) if denominator else None


def cycles(values: list[int]) -> Json:
    if not values:
        return {"samples": 0, "mean_ticks": None, "p95_ticks": None}
    ordered = sorted(integer(value) for value in values)
    index = Fraction(95, 100) * (len(ordered) - 1)
    lower = index.numerator // index.denominator
    upper = min(lower + 1, len(ordered) - 1)
    p95 = ordered[lower] + (index - lower) * (ordered[upper] - ordered[lower])
    return {
        "samples": len(ordered),
        "mean_ticks": ratio(sum(ordered), len(ordered)),
        "p95_ticks": record(p95),
    }


def business(rows: list[Json], offers: dict[str, tuple[int, int]], key: str, tick: int) -> Json:
    if len(rows) != len(offers) or {row[key] for row in rows} != set(offers):
        raise ValueError("Coordinator metric order identities differ")
    completed: list[Json] = []
    arrived, unadmitted, unfinished = 0, 0, 0
    for row in rows:
        arrival, _ = offers[row[key]]
        for field in ("admitted_tick", "shipped_tick"):
            if row[field] is not None and not arrival <= integer(row[field]) <= tick:
                raise ValueError("Coordinator metric transition exceeds observation")
        if row["shipped_tick"] is not None:
            if row["admitted_tick"] is None or row["shipped_tick"] < row["admitted_tick"]:
                raise ValueError("Business handover must follow admission")
            completed.append(row)
        if arrival <= tick:
            arrived += 1
            unadmitted += (tick if row["admitted_tick"] is None else row["admitted_tick"]) - arrival
            unfinished += (tick if row["shipped_tick"] is None else row["shipped_tick"]) - arrival
    return {
        "arrived_orders": arrived,
        "completed_orders": len(completed),
        "backlog_orders": arrived - len(completed),
        "completed_units": sum(offers[row[key]][1] for row in completed),
        "cycle": cycles([row["shipped_tick"] - offers[row[key]][0] for row in completed]),
        "queues": {
            "unadmitted_order_ticks": unadmitted,
            "unfinished_order_ticks": unfinished,
            "mean_unadmitted_orders": ratio(unadmitted, tick),
            "mean_unfinished_orders": ratio(unfinished, tick),
        },
    }
