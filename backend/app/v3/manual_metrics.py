"""Settled business counts, exact cycle statistics and measured resource exposure."""

from fractions import Fraction
from typing import Any

from app.v3.execution_types import ExecutionProfile, ManualEvent, ManualOutcome, ManualSnapshot
from app.v3.manual_metrics_resources import busy_integrals, queue_integrals
from app.v3.runtime_time import TICKS_PER_SECOND


def cycle_statistics(ticks: tuple[int, ...]) -> dict[str, float | None]:
    if any(type(value) is not int or value < 0 for value in ticks):
        raise ValueError("cycle duration must be nonnegative integer ticks")
    if not ticks:
        return {"mean_cycle_s": None, "p95_cycle_s": None}
    values = sorted(ticks)
    index = Fraction(95, 100) * (len(values) - 1)
    lower = index.numerator // index.denominator
    upper = min(lower + 1, len(values) - 1)
    percentile = values[lower] + (index - lower) * (values[upper] - values[lower])
    return {
        "mean_cycle_s": float(Fraction(sum(values), len(values) * TICKS_PER_SECOND)),
        "p95_cycle_s": float(percentile / TICKS_PER_SECOND),
    }


def _completions(
    profile: ExecutionProfile, events: tuple[ManualEvent, ...], end: int
) -> dict[str, int]:
    jobs = {job.job_id: job for job in profile.jobs}
    completed: dict[str, int] = {}
    for event in events:
        if event.tick > end:
            break
        if event.kind != "hu_owner_changed" or event.owner is None:
            continue
        job = jobs[event.job_id]
        kind = "stock" if job.direction == "inbound" else "shipped"
        if event.owner.kind == kind:
            completed.setdefault(job.job_id, event.tick)
    return completed


def _business(
    profile: ExecutionProfile, events: tuple[ManualEvent, ...], end: int
) -> dict[str, Any]:
    completed = _completions(profile, events, end)
    hus = {hu.hu_id: hu for hu in profile.handling_units}
    result = {}
    for direction in ("inbound", "outbound"):
        jobs = [
            job for job in profile.jobs if job.direction == direction and job.arrival_tick <= end
        ]
        done = [job for job in jobs if job.job_id in completed]
        cycles = tuple(completed[job.job_id] - job.arrival_tick for job in done)
        result[direction] = {
            "arrived_hus": len(jobs),
            "completed_hus": len(done),
            "backlog_hus": len(jobs) - len(done),
            "completed_units": sum(hus[job.hu_id].quantity for job in done),
            "completed_mass_kg": float(
                sum((hus[job.hu_id].gross_mass_kg for job in done), Fraction())
            ),
            **cycle_statistics(cycles),
        }
    return result


def _window(
    profile: ExecutionProfile, outcome: ManualOutcome, snapshot: ManualSnapshot
) -> dict[str, Any]:
    end = snapshot.tick
    return {
        "tick": end,
        "time_s": end / TICKS_PER_SECOND,
        "operational_status": snapshot.status,
        **_business(profile, outcome.events, end),
        **busy_integrals(profile, outcome.events, end),
        "queues": queue_integrals(profile, outcome.events, end),
    }


def summary(profile: ExecutionProfile, outcome: ManualOutcome) -> dict[str, Any]:
    if profile.profile_id != outcome.profile_id:
        raise ValueError("manual outcome/profile identity mismatch")
    return {
        "metrics_version": "qoima-manual-metrics-v1",
        "counts_boundary": "settled_tick_inclusive",
        "integral_window": "[0,T)",
        "cycle_completion": "inbound_putaway_or_outbound_handover",
        "at_horizon": _window(profile, outcome, outcome.at_horizon),
        "at_end": _window(profile, outcome, outcome.at_end),
    }
