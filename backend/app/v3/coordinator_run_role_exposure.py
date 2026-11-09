"""Integrate observed assignments and declared availability; assignment is not paid work."""

from itertools import pairwise

from app.v3.coordinator_models import ActorRoleView, CoordinatorProfile, RoleExposure, RoleView
from app.v3.staff_registry_values import ROLES


def available(profile: CoordinatorProfile, actor: str, tick: int) -> bool:
    spec = next(a for a in profile.world.receipts.flow.actors if a.actor_id == actor)
    return spec.available_tick <= tick and not any(
        w.actor_id == actor and w.start_tick <= tick < w.end_tick
        for w in profile.registry.unavailability
    )


def historical_role(
    profile: CoordinatorProfile, roles: tuple[RoleView, ...], actor: str, tick: int
) -> str:
    primary = next(w.primary_role for w in profile.registry.workers if w.actor_id == actor)
    active = [
        r
        for r in roles
        if r.actor_id == actor
        and r.departed_tick is not None
        and r.departed_tick <= tick
        and (r.restored_tick is None or tick < r.restored_tick)
    ]
    if len(active) > 1:
        raise ValueError("Historical role assignments overlap on the physical actor")
    if not active:
        return primary
    view = active[0]
    if view.activated_tick is None or tick < view.activated_tick:
        return "transition"
    if view.return_started_tick is not None and view.return_started_tick <= tick:
        return "transition"
    return "pack"


def exposure(profile: CoordinatorProfile, roles: tuple[RoleView, ...], tick: int) -> RoleExposure:
    boundaries = {0, tick}
    for spec in profile.world.receipts.flow.actors:
        boundaries.add(min(tick, spec.available_tick))
    for window in profile.registry.unavailability:
        boundaries.update((min(tick, window.start_tick), min(tick, window.end_tick)))
    for view in roles:
        boundaries.update(
            t
            for t in (
                view.departed_tick,
                view.activated_tick,
                view.return_started_tick,
                view.restored_tick,
            )
            if t is not None and t <= tick
        )
    totals = dict.fromkeys((*ROLES, "transition", "unavailable"), 0)
    for start, end in pairwise(sorted(boundaries)):
        for worker in profile.registry.workers:
            role = historical_role(profile, roles, worker.actor_id, start)
            category = role if available(profile, worker.actor_id, start) else "unavailable"
            totals[category] += end - start
    return RoleExposure(
        tuple((role, totals[role]) for role in ROLES), totals["transition"], totals["unavailable"]
    )


def actor_roles(
    profile: CoordinatorProfile, roles: tuple[RoleView, ...], tick: int
) -> tuple[ActorRoleView, ...]:
    result = []
    for worker in sorted(profile.registry.workers, key=lambda w: w.actor_id):
        assigned = [
            r
            for r in roles
            if r.actor_id == worker.actor_id
            and r.status not in {"unreleased", "restored", "rejected"}
        ]
        if len(assigned) > 1:
            raise ValueError("Captured role assignments overlap on one actor")
        result.append(
            ActorRoleView(
                worker.actor_id,
                worker.primary_role,
                historical_role(profile, roles, worker.actor_id, tick),
                available(profile, worker.actor_id, tick),
                assigned[0].intent_id if assigned else None,
            )
        )
    return tuple(result)
