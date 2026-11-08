"""Paid work and assigned waiting from actual half-open native observations."""

from collections import Counter
from typing import Any

from app.v3.light_flow_models import FlowSnapshot
from app.v3.runtime_time import TICKS_PER_SECOND

ROLE_PREFIX = {"P": "pick", "K": "pack", "R": "receive", "S": "ship", "F": "forklift"}


def resources(snapshot: FlowSnapshot) -> dict[str, Any]:
    until = snapshot.tick
    paid = {worker.actor_id: worker.paid_ticks for worker in snapshot.workers}
    counts: Counter[str] = Counter()
    totals = dict.fromkeys(ROLE_PREFIX.values(), 0)
    for identity, value in sorted(paid.items()):
        role = ROLE_PREFIX[identity[0]]
        counts[role] += 1
        totals[role] += value
    return {
        "worker_paid_s": sum(paid.values()) / TICKS_PER_SECOND,
        "worker_paid_s_by_actor": {
            identity: value / TICKS_PER_SECOND for identity, value in sorted(paid.items())
        },
        "worker_utilization_by_actor": {
            identity: value / until if until else None for identity, value in sorted(paid.items())
        },
        "roster_utilization": sum(paid.values()) / (until * len(paid)) if until and paid else None,
        "role_pool_size": dict(sorted(counts.items())),
        "role_paid_s": {role: value / TICKS_PER_SECOND for role, value in sorted(totals.items())},
        "role_pool_utilization": {
            role: value / (until * counts[role]) if until and counts[role] else None
            for role, value in sorted(totals.items())
        },
    }


def resource_waits(snapshot: FlowSnapshot) -> dict[str, float | None]:
    waiting = sum(worker.queue_ticks for worker in snapshot.workers)
    stopped = snapshot.belt.queue_ticks
    return {
        "assigned_worker_wait_person_seconds": waiting / TICKS_PER_SECOND,
        "mean_waiting_workers": waiting / snapshot.tick if snapshot.tick else None,
        "stopped_belt_carrier_seconds": stopped / TICKS_PER_SECOND,
        "mean_stopped_belt_carriers": stopped / snapshot.tick if snapshot.tick else None,
    }
