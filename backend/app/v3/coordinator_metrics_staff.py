"""Assignment exposure and paid work are separate populations on one actual worker map."""

from typing import TypedDict

from app.v3.coordinator_metrics_values import integer, ratio
from app.v3.coordinator_metrics_work import paid_by_role
from app.v3.coordinator_models import CoordinatorOutcome, CoordinatorProfile, CoordinatorSnapshot
from app.v3.execution_types import ACTOR_IDS
from app.v3.interface import Json
from app.v3.staff_registry_values import ROLES


class _ActorLabor(TypedDict):
    actor_id: str
    primary_role: str
    paid_ticks: int
    assigned_wait_ticks: int


def assignment(snapshot: CoordinatorSnapshot) -> Json:
    exposure = snapshot.exposure
    values = dict(exposure.role_ticks)
    if len(exposure.role_ticks) != len(ROLES) or set(values) != set(ROLES):
        raise ValueError("Coordinator role exposure identities differ")
    totals = [integer(value) for value in values.values()]
    transition = integer(exposure.transition_ticks)
    unavailable = integer(exposure.unavailable_ticks)
    if sum(totals) + transition + unavailable != 24 * snapshot.tick:
        raise ValueError("Coordinator role exposure must partition all 24 workers")
    return {
        "role_ticks": values,
        "transition_ticks": transition,
        "unavailable_ticks": unavailable,
        "scope": "available_assignment_time_not_busy_utilization",
    }


def labor(
    profile: CoordinatorProfile, outcome: CoordinatorOutcome, snapshot: CoordinatorSnapshot
) -> Json:
    if len(snapshot.workers) != 24 or {w.actor_id for w in snapshot.workers} != set(ACTOR_IDS):
        raise ValueError("Coordinator metrics require the unchanged 24 workers")
    primary = {w.actor_id: w.primary_role for w in profile.registry.workers}
    actors: list[_ActorLabor] = []
    for worker in snapshot.workers:
        paid, waiting = integer(worker.paid_ticks), integer(worker.queue_ticks)
        if paid + waiting > snapshot.tick:
            raise ValueError("Coordinator paid and waiting exposure exceed the observed clock")
        actors.append(
            {
                "actor_id": worker.actor_id,
                "primary_role": primary[worker.actor_id],
                "paid_ticks": paid,
                "assigned_wait_ticks": waiting,
            }
        )
    paid = sum(row["paid_ticks"] for row in actors)
    waiting = sum(row["assigned_wait_ticks"] for row in actors)
    roles = paid_by_role(profile, outcome, snapshot)
    if sum(roles.values()) != paid:
        raise ValueError("Actual paid operation intervals differ from once-counted worker labor")
    denominators = dict(snapshot.exposure.role_ticks)
    denominators["transition"] = snapshot.exposure.transition_ticks
    available = 24 * snapshot.tick - snapshot.exposure.unavailable_ticks
    return {
        "paid_ticks": paid,
        "assigned_wait_ticks": waiting,
        "assigned_exposure_ticks": paid + waiting,
        "role_transition_paid_ticks": roles["transition"],
        "roster_paid_fraction": ratio(paid, 24 * snapshot.tick),
        "available_roster_paid_fraction": ratio(paid, available),
        "paid_ticks_by_effective_role": roles,
        "role_paid_fraction": {
            role: ratio(value, denominators[role]) for role, value in roles.items()
        },
        "actors": actors,
    }
