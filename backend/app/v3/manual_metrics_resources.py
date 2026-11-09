"""Exact worker-lease and queue integrals over half-open observation windows."""

from collections import defaultdict
from fractions import Fraction
from typing import Any

from app.v3.execution_types import ExecutionProfile, ManualEvent
from app.v3.runtime_time import TICKS_PER_SECOND


def _seconds(ticks: int) -> float:
    return float(Fraction(ticks, TICKS_PER_SECOND))


def _eligible_counts(profile: ExecutionProfile) -> dict[str, int]:
    actors = {actor.actor_id: actor for actor in profile.actors}
    result = {}
    for role, direction in (("receive", "inbound"), ("ship", "outbound")):
        members = {
            actor_id
            for port in profile.ports
            if port.direction == direction
            for actor_id in port.eligible_actor_ids
        }
        result[role] = sum(role in actors[actor_id].skills for actor_id in members)
    return result


def busy_integrals(
    profile: ExecutionProfile, events: tuple[ManualEvent, ...], end: int
) -> dict[str, Any]:
    active: dict[str, tuple[int, str]] = {}
    jobs = {job.job_id: job for job in profile.jobs}
    by_actor: dict[str, int] = dict.fromkeys((a.actor_id for a in profile.actors), 0)
    by_role = {"receive": 0, "ship": 0}
    for event in events:
        if event.tick > end:
            break
        for resource in event.resource_ids:
            if not resource.startswith("worker:"):
                continue
            actor = resource.removeprefix("worker:")
            if event.kind == "lease_acquired":
                if actor in active:
                    raise ValueError("overlapping worker leases")
                active[actor] = event.tick, event.job_id
            elif event.kind == "lease_released":
                start, job_id = active.pop(actor)
                duration = event.tick - start
                by_actor[actor] += duration
                by_role["receive" if jobs[job_id].direction == "inbound" else "ship"] += duration
    for actor, (start, job_id) in active.items():
        duration = end - start
        by_actor[actor] += duration
        by_role["receive" if jobs[job_id].direction == "inbound" else "ship"] += duration
    workers = len(profile.actors)
    eligible = _eligible_counts(profile)
    return {
        "worker_busy_s": _seconds(sum(by_actor.values())),
        "worker_busy_s_by_actor": {
            actor: _seconds(value) for actor, value in sorted(by_actor.items())
        },
        "roster_utilization": sum(by_actor.values()) / (end * workers) if end and workers else None,
        "role_busy_s": {role: _seconds(value) for role, value in by_role.items()},
        "role_pool_utilization": {
            role: value / (end * eligible[role]) if end and eligible[role] else None
            for role, value in by_role.items()
        },
    }


def queue_integrals(
    profile: ExecutionProfile, events: tuple[ManualEvent, ...], end: int
) -> dict[str, Any]:
    ports = {job.job_id: job.port_id for job in profile.jobs}
    totals = dict.fromkeys((port.port_id for port in profile.ports), 0)
    reasons: dict[str, dict[str, int]] = {port: defaultdict(int) for port in totals}
    waiting: dict[str, tuple[int, str]] = {}

    def close(job_id: str, tick: int) -> None:
        if job_id in waiting:
            start, reason = waiting.pop(job_id)
            duration = tick - start
            totals[ports[job_id]] += duration
            reasons[ports[job_id]][reason] += duration

    for event in events:
        if event.tick >= end:
            break
        if event.job is not None:
            job = event.job
            close(job.job_id, event.tick)
            if job.state in {"waiting", "active"} and job.wait_reason is not None:
                waiting[job.job_id] = event.tick, job.wait_reason
    for job_id in tuple(waiting):
        close(job_id, end)
    return {
        port: {
            "job_seconds": _seconds(value),
            "mean_jobs": value / end if end else None,
            "wait_seconds_by_reason": {
                reason: _seconds(ticks) for reason, ticks in sorted(reasons[port].items())
            },
        }
        for port, value in sorted(totals.items())
    }
