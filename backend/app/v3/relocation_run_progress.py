"""Causal N1 progress replay couples contiguous effects, claims, leases, and paid stages."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from app.v3.coordinator_run_inventory import same
from app.v3.coordinator_run_role_exposure import available
from app.v3.light_flow_models import FlowEvent, FlowOperation
from app.v3.relocation_models import RelocationPlan, RelocationProfile
from app.v3.relocation_observe import RelocationEvent, RelocationSnapshot, RelocationView
from app.v3.relocation_run_resources import required

if TYPE_CHECKING:
    from app.v3.relocation_run_validation import RelocationJournal


class RelocationProgress:
    def __init__(
        self, profile: RelocationProfile, plans: tuple[RelocationPlan, ...], horizon: int
    ) -> None:
        self.profile, self.horizon = profile, horizon
        self.plans = {p.job.job_id: p for p in plans}
        self.views = {p.job.job_id: _initial(p) for p in plans}
        self.derived: dict[str, str] = {}
        self.next_events: list[tuple[str, str | None]] = []
        self.transition: tuple[str, int] | None = None
        self.pending_completion = False
        self.advanced = False

    def before(self, event: FlowEvent, journal: RelocationJournal) -> None:
        self._next(event)
        if event.order_id not in self.plans:
            return
        if type(event) is not RelocationEvent:
            raise ValueError("Exact relocation progress event required")
        plan, view = self.plans[event.order_id], self.views[event.order_id]
        if event.actor_id != plan.job.actor_id:
            raise ValueError("Relocation event changed its immutable actor")
        self._transition_event(event, plan, view, journal)
        same(
            event.relocation,
            self.views[event.order_id],
            "Relocation event invents physical progress",
        )

    def _next(self, event: FlowEvent) -> None:
        if not self.next_events:
            return
        kind, resource = self.next_events.pop(0)
        actual_resource = event.resource_id if isinstance(event, RelocationEvent) else None
        if (event.order_id, event.tick) != self.transition or (event.kind, actual_resource) != (
            kind,
            resource,
        ):
            raise ValueError("Relocation transition lost its contiguous causal fact")

    def _expect(self, event: RelocationEvent, rows: list[tuple[str, str | None]]) -> None:
        if self.next_events:
            raise ValueError("Relocation transition overlaps unfinished evidence")
        self.transition, self.next_events = (event.order_id, event.tick), rows

    def _transition_event(
        self,
        event: RelocationEvent,
        plan: RelocationPlan,
        view: RelocationView,
        journal: RelocationJournal,
    ) -> None:
        key, kind = event.order_id, event.kind
        if kind == "relocation_arrived":
            if view.status != "unreleased" or event.tick != plan.job.arrival_tick:
                raise ValueError("Duplicate or premature relocation arrival")
            self.views[key] = replace(view, status="waiting")
        elif kind == "relocation_wait_changed":
            reason = wait_reason(self.profile, plan, journal, event.tick)
            if view.status != "waiting" or reason == view.wait_reason:
                raise ValueError("Relocation wait fact has no actual changed impediment")
            self.views[key] = replace(view, wait_reason=reason)
        elif kind == "inventory_claim_acquired":
            self._admit(event, plan, view, journal)
        elif kind == "operation_completed":
            self._completed(event, plan, view)
        elif kind in {"relocation_taken", "relocation_placed"}:
            self._effect(event, plan, view)
        elif kind == "relocation_state_changed":
            self._changed(event, plan, view, journal)
        elif kind == "inventory_claim_released":
            if view.completed_steps != 5 or view.returned_tick is not None:
                raise ValueError("Relocation claim released before paid return")
            self.views[key] = replace(view, status="complete", returned_tick=event.tick)
        elif kind == "relocation_returned":
            if view.returned_tick != event.tick or view.status != "complete":
                raise ValueError("Relocation return has no completed release sequence")
        elif kind == "operation_started":
            self._started(event, plan, view)

    def _admit(
        self,
        event: RelocationEvent,
        plan: RelocationPlan,
        view: RelocationView,
        journal: RelocationJournal,
    ) -> None:
        if view.status != "waiting" or not plan.job.arrival_tick <= event.tick < self.horizon:
            raise ValueError("Relocation claim has no eligible admission")
        if wait_reason(self.profile, plan, journal, event.tick) is not None:
            raise ValueError("Relocation atomically acquired conflicting physical resources")
        self.views[event.order_id] = replace(
            view, status="approaching", admitted_tick=event.tick, wait_reason=None
        )
        self._expect(
            event,
            [("relocation_resource_acquired", r) for r in required(plan)]
            + [("relocation_admitted", None)],
        )

    def _started(self, event: RelocationEvent, plan: RelocationPlan, view: RelocationView) -> None:
        if view.admitted_tick is None or view.completed_steps >= len(plan.steps):
            raise ValueError("Relocation operation has no unfinished admitted plan")
        expected = view.admitted_tick + sum(s.duration for s in plan.steps[: view.completed_steps])
        if event.tick != expected:
            raise ValueError("Relocation paid operation starts at an invented clock")

    def _completed(
        self, event: RelocationEvent, plan: RelocationPlan, view: RelocationView
    ) -> None:
        if view.admitted_tick is None or view.completed_steps >= len(plan.steps):
            raise ValueError("Relocation completion has no unfinished admitted plan")
        step = plan.steps[view.completed_steps]
        if event.operation is None or event.operation.kind != step.kind or step.duration <= 0:
            raise ValueError("Relocation completion skipped its next paid step")
        expected = view.admitted_tick + sum(
            s.duration for s in plan.steps[: view.completed_steps + 1]
        )
        if event.tick != expected:
            raise ValueError("Relocation completion changed its paid clock")
        self.pending_completion, self.advanced = True, False
        effect = {
            "relocation_take": "relocation_taken",
            "relocation_place": "relocation_placed",
        }.get(step.kind)
        rows = [] if effect is None else [(effect, None)]
        self._expect(event, [*rows, ("relocation_state_changed", None)])

    def _effect(self, event: RelocationEvent, plan: RelocationPlan, view: RelocationView) -> None:
        if not self.pending_completion or self.advanced:
            raise ValueError("Relocation stock effect lacks one completed handling")
        required_kind = (
            "relocation_take" if event.kind == "relocation_taken" else "relocation_place"
        )
        if plan.steps[view.completed_steps].kind != required_kind:
            raise ValueError("Relocation effect differs from completed step")
        self._advance(event, plan, view)
        self.advanced = True

    def _changed(
        self,
        event: RelocationEvent,
        plan: RelocationPlan,
        view: RelocationView,
        journal: RelocationJournal,
    ) -> None:
        if not self.pending_completion:
            if view.admitted_tick is None or view.completed_steps >= len(plan.steps):
                raise ValueError("Relocation progress has no actual next step")
            step = plan.steps[view.completed_steps]
            worker = journal.motion.workers[plan.job.actor_id]
            expected = view.admitted_tick + sum(
                s.duration for s in plan.steps[: view.completed_steps]
            )
            if (
                step.duration != 0
                or worker.node != step.target
                or worker.operation is not None
                or event.tick != expected
            ):
                raise ValueError("Relocation progress lacks actual completed motion")
        if not self.advanced:
            self._advance(event, plan, view)
        self.pending_completion, self.advanced = False, False
        if self.views[event.order_id].completed_steps == 5:
            self._expect(
                event,
                [
                    ("inventory_claim_released", None),
                    *(("relocation_resource_released", r) for r in required(plan)),
                    ("relocation_returned", None),
                ],
            )

    def _advance(self, event: RelocationEvent, plan: RelocationPlan, view: RelocationView) -> None:
        count = view.completed_steps + 1
        status = ("approaching", "taking", "carrying", "placing", "returning", "returning")[count]
        taken = event.tick if count == 2 else view.taken_tick
        placed = event.tick if count == 4 else view.placed_tick
        self.views[event.order_id] = replace(
            view, completed_steps=count, status=status, taken_tick=taken, placed_tick=placed
        )
        if count == 4:
            self.derived[plan.job.hu_id] = plan.job.to_slot_id

    def settle(self, tick: int, journal: RelocationJournal) -> None:
        if self.next_events or self.pending_completion:
            raise ValueError("Settled relocation retains an incomplete causal transition")
        for key, view in self.views.items():
            plan = self.plans[key]
            if view.status == "unreleased" and plan.job.arrival_tick <= tick:
                raise ValueError("Declared relocation arrival is absent")
            if view.status == "waiting" and tick < self.horizon:
                reason = wait_reason(self.profile, plan, journal, tick)
                if reason is None or reason != view.wait_reason:
                    raise ValueError("Waiting relocation lacks its actual admission impediment")
            _custody(plan, view, journal)
            _active_operation(plan, view, journal, tick)

    def check(self, state: RelocationSnapshot) -> None:
        same(state.relocations, tuple(self.views.values()), "Captured relocation progress differs")
        same(
            state.derived_sources,
            tuple(sorted(self.derived.items())),
            "Captured derived sources differ",
        )


def _initial(plan: RelocationPlan) -> RelocationView:
    job = plan.job
    return RelocationView(
        job.job_id,
        job.hu_id,
        job.actor_id,
        job.from_slot_id,
        job.to_slot_id,
        "unreleased",
        None,
        None,
        None,
        None,
        0,
        None,
    )


def _active_operation(
    plan: RelocationPlan, view: RelocationView, journal: RelocationJournal, tick: int
) -> None:
    if view.admitted_tick is None or view.returned_tick is not None:
        return
    count = view.completed_steps
    if not 0 <= count < len(plan.steps):
        raise ValueError("Relocation unfinished operation has no next declared step")
    step = plan.steps[count]
    start = view.admitted_tick + sum(s.duration for s in plan.steps[:count])
    if step.duration <= 0 or not start <= tick < start + step.duration:
        raise ValueError("Relocation next operation is not open at its exact paid clock")
    source = plan.actor.home if count == 0 else plan.steps[count - 1].target
    expected = FlowOperation(
        step.kind,
        plan.job.job_id,
        start,
        start + step.duration,
        source,
        step.target,
        step.route,
        step.carrying_id,
        step.cart_id,
    )
    worker = journal.motion.workers[plan.job.actor_id]
    same(worker.operation, expected, "Relocation next operation is missing or changed")
    if (
        worker.order_id != plan.job.job_id
        or worker.waiting_since is not None
        or worker.node != (None if step.route is not None else step.target)
    ):
        raise ValueError("Relocation open operation lost its assigned physical actor")


def wait_reason(
    profile: RelocationProfile, plan: RelocationPlan, journal: RelocationJournal, tick: int
) -> str | None:
    ledger, job = journal.inventory.ledger, plan.job
    contents = ledger.contents(job.hu_id)
    if any(c.container_id == job.hu_id for c in ledger.claims):
        return "stock_claimed"
    if contents.container.owner_id != job.from_slot_id:
        return "source_moved"
    if {u.token.unit_id for u in contents.units} != set(plan.unit_ids):
        return "stock_not_intact"
    if any(c.owner_id == job.to_slot_id for c in ledger.snapshot().containers) or any(
        p + job.to_slot_id in journal.resources.leases
        for p in ("receipt:place:", "whole:place:", "relocation:place:")
    ):
        return "destination_busy"
    if _worker_busy(profile, plan, journal, tick):
        return "worker_busy"
    if journal.motion.workers[job.actor_id].node != plan.actor.home:
        return "worker_not_home"
    finish = tick + sum(s.duration for s in plan.steps)
    if any(
        w.actor_id == job.actor_id and w.start_tick < finish and w.end_tick > tick
        for w in profile.coordinator.registry.unavailability
    ):
        return "worker_window"
    if any(
        i.actor_id == job.actor_id and i.request_tick < finish and i.restore_by_tick > tick
        for i in profile.coordinator.intents
    ):
        return "role_window"
    return None


def _worker_busy(
    profile: RelocationProfile, plan: RelocationPlan, journal: RelocationJournal, tick: int
) -> bool:
    actor = plan.job.actor_id
    worker = journal.motion.workers[actor]
    capability = next(w for w in profile.coordinator.registry.workers if w.actor_id == actor)
    if (
        worker.order_id is not None
        or worker.operation is not None
        or worker.waiting_since is not None
        or not available(profile.coordinator, actor, tick)
        or capability.primary_role != "ship"
        or "ship" not in capability.eligible_roles
    ):
        return True
    if any(
        v.actor_id == actor and v.status not in {"unreleased", "restored", "rejected"}
        for v in journal.roles.views.values()
    ):
        return True
    if any(c.owner_id == "actor:" + actor for c in journal.inventory.ledger.snapshot().containers):
        return True
    return any(
        p + actor in journal.resources.leases
        for p in (
            "receipt:worker:",
            "whole:worker:",
            "pack:worker:",
            "relocation:worker:",
        )
    )


def _custody(plan: RelocationPlan, view: RelocationView, journal: RelocationJournal) -> None:
    if view.admitted_tick is None:
        return
    job = plan.job
    claim = next(
        (c for c in journal.inventory.ledger.claims if c.claim_id == "relocation:" + job.job_id),
        None,
    )
    if (claim is None) != (view.returned_tick is not None):
        raise ValueError("Relocation claim lifetime differs from actual paid return")
    active = view.returned_tick is None
    for resource in required(plan):
        if (journal.resources.leases.get(resource) == job.job_id) != active:
            raise ValueError("Relocation reservation lifetime differs from paid return")
    if view.returned_tick is not None and any(
        s.spec.hu_id == job.hu_id and s.admitted_tick is not None
        for s in journal.goods.whole.values()
    ):
        return
    contents = journal.inventory.ledger.contents(job.hu_id)
    owner = (
        job.to_slot_id
        if view.placed_tick is not None
        else "actor:" + job.actor_id
        if view.taken_tick is not None
        else job.from_slot_id
    )
    if contents.container.owner_id != owner or contents.gross_mass_kg != plan.gross_mass_kg:
        raise ValueError("Relocation actual custody differs from completed handling")
    if {u.token.unit_id for u in contents.units} != set(plan.unit_ids):
        raise ValueError("Relocation lost intact original unit identities")
