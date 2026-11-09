"""Observed helper work and paid restoration, never inferred from assignment exposure."""

from typing import Any

from app.v3.coordinator_models import (
    CoordinatorEvent,
    CoordinatorOutcome,
    CoordinatorProfile,
    RoleIntent,
    RoleView,
)
from app.v3.coordinator_packing_models import PackingView
from app.v3.flow_profile_wire import record
from app.v3.light_flow_models import FlowEvent


def helper_evidence(
    profile: CoordinatorProfile,
    outcome: CoordinatorOutcome,
) -> list[dict[str, Any]]:
    return [
        _helper(intent, outcome) for intent in sorted(profile.intents, key=lambda i: i.intent_id)
    ]


def _helper(intent: RoleIntent, outcome: CoordinatorOutcome) -> dict[str, Any]:
    role = next(view for view in outcome.at_end.roles if view.intent_id == intent.intent_id)
    packing = _matching_packing(intent, outcome)
    completed = [view for view in packing if _packing_complete(view, outcome)]
    orders = {view.order_id for view in packing}
    packing_paid = _paid(outcome, intent.actor_id, orders, {"pack", "clear"})
    transition_paid = _paid(
        outcome, intent.actor_id, {intent.intent_id}, {"role_outward", "role_return"}
    )
    restored = role.restored_tick
    transitions = _transition(
        outcome, role, "role_outward", role.departed_tick, role.activated_tick
    ) and _transition(outcome, role, "role_return", role.return_started_tick, restored)
    demonstrated = (
        bool(completed)
        and packing_paid > 0
        and role.activated_tick is not None
        and restored is not None
        and restored <= intent.restore_by_tick
        and transitions
        and role.status == "restored"
        and not outcome.constraint_violations
    )
    return {
        **record(role),
        "planned_restore_by_tick": intent.restore_by_tick,
        "packing_paid_ticks": packing_paid,
        "transition_paid_ticks": transition_paid,
        "completed_role_transitions": transitions,
        "completed_orders": len(completed),
        "demonstrated": demonstrated,
    }


def _transition(
    outcome: CoordinatorOutcome,
    role: RoleView,
    kind: str,
    start: int | None,
    end: int | None,
) -> bool:
    if start is None or end is None or not 0 <= start <= end <= outcome.observation_end_tick:
        return False
    if start < end:
        return _completed(outcome, role.actor_id, role.intent_id, kind, end)
    event_kind = "role_activated" if kind == "role_outward" else "role_restored"
    return any(
        isinstance(event, CoordinatorEvent)
        and event.kind == event_kind
        and event.tick == end
        and event.actor_id == role.actor_id
        and event.order_id == role.intent_id
        and event.role_view is not None
        and (event.role_view.intent_id, event.role_view.actor_id, event.role_view.station_id)
        == (role.intent_id, role.actor_id, role.station_id)
        and (
            event.role_view.activated_tick
            if kind == "role_outward"
            else event.role_view.restored_tick
        )
        == end
        for event in outcome.events
    )


def _matching_packing(intent: RoleIntent, outcome: CoordinatorOutcome) -> tuple[PackingView, ...]:
    return tuple(
        view
        for view in outcome.at_end.packing
        if (view.role_intent_id, view.actor_id, view.station_id)
        == (intent.intent_id, intent.actor_id, intent.station_id)
    )


def _packing_complete(view: PackingView, outcome: CoordinatorOutcome) -> bool:
    return (
        view.packed_tick is not None
        and view.cleared_tick is not None
        and view.released_tick is not None
        and _completed(outcome, view.actor_id, view.order_id, "pack", view.packed_tick)
        and _completed(outcome, view.actor_id, view.order_id, "clear", view.cleared_tick)
    )


def _completed(
    outcome: CoordinatorOutcome, actor: str, job: str, kind: str, tick: int | None
) -> bool:
    return (
        tick is not None
        and tick <= outcome.observation_end_tick
        and any(
            event.kind == "operation_completed"
            and event.tick == tick
            and event.actor_id == actor
            and event.operation is not None
            and event.operation.order_id == job
            and event.operation.kind == kind
            and event.operation.planned_end_tick == tick
            for event in outcome.events
        )
    )


def _paid(outcome: CoordinatorOutcome, actor: str, jobs: set[str], kinds: set[str]) -> int:
    cutoff = outcome.observation_end_tick
    return sum(
        _observed_duration(event, cutoff)
        for event in outcome.events
        if event.kind == "operation_started"
        and event.actor_id == actor
        and event.operation is not None
        and event.operation.order_id in jobs
        and event.operation.kind in kinds
    )


def _observed_duration(event: FlowEvent, cutoff: int) -> int:
    operation = event.operation
    if operation is None:
        return 0
    return max(0, min(cutoff, operation.planned_end_tick) - operation.start_tick)
