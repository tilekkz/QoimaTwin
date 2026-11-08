"""Observed paid intervals classified by the actor's actual effective role at operation start."""

from app.v3.coordinator_metrics_values import integer
from app.v3.coordinator_models import CoordinatorOutcome, CoordinatorProfile, CoordinatorSnapshot
from app.v3.staff_registry_values import ROLES


def _role(profile: CoordinatorProfile, snapshot: CoordinatorSnapshot, actor: str, tick: int) -> str:
    primary = next(w.primary_role for w in profile.registry.workers if w.actor_id == actor)
    active = []
    for view in snapshot.roles:
        if view.actor_id != actor or view.departed_tick is None or tick < view.departed_tick:
            continue
        if view.restored_tick is not None and tick >= view.restored_tick:
            continue
        active.append(view)
    if len(active) > 1:
        raise ValueError("Coordinator paid actor has overlapping role assignments")
    if not active:
        return primary
    view = active[0]
    if view.activated_tick is None or tick < view.activated_tick:
        return "transition"
    if view.return_started_tick is not None and tick >= view.return_started_tick:
        return "transition"
    return "pack"


def paid_by_role(
    profile: CoordinatorProfile, outcome: CoordinatorOutcome, snapshot: CoordinatorSnapshot
) -> dict[str, int]:
    result: dict[str, int] = dict.fromkeys((*ROLES, "transition"), 0)
    actors = {worker.actor_id for worker in profile.registry.workers}
    for event in outcome.events:
        operation = event.operation
        if event.kind != "operation_started" or operation is None:
            continue
        start, end = integer(operation.start_tick), integer(operation.planned_end_tick)
        if end <= start or event.tick != start or event.actor_id not in actors:
            raise ValueError("Coordinator paid interval has invalid actual actor or clock")
        if start >= snapshot.tick:
            continue
        actor = str(event.actor_id)
        role = _role(profile, snapshot, actor, start)
        if operation.kind in {"role_outward", "role_return"} and role != "transition":
            raise ValueError("Coordinator paid transition lacks its actual role assignment")
        result[role] += min(snapshot.tick, end) - start
    return result
