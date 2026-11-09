"""Opt-in N1 uses the existing coordinator calendar, physical ledger, and worker objects."""

from __future__ import annotations

import heapq
from collections.abc import Callable

from app.v3 import coordinator_observe
from app.v3 import relocation_invariants as invariants
from app.v3 import relocation_observe as observe
from app.v3 import relocation_runtime as runtime
from app.v3.conveyor_models import ConveyorSource
from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.coordinator_models import CoordinatorOutcome, CoordinatorSnapshot
from app.v3.light_flow_engine import LightFlowEngine
from app.v3.light_flow_models import FlowSnapshot
from app.v3.light_flow_state import HumanState, HumanStep
from app.v3.relocation_models import RelocationProfile
from app.v3.relocation_plan import plan_relocations
from app.v3.stock_claims import StockClaim
from app.v3.stock_models import StockDelta


class RelocationEngine(CoordinatorEngine):
    def __init__(
        self,
        profile: RelocationProfile,
        conveyor: ConveyorSource,
        *,
        on_tick_settled: Callable[[FlowSnapshot, int], None] | None = None,
    ) -> None:
        plans = plan_relocations(profile)
        self.relocation_profile = profile
        self.relocation_authority = invariants.authority(profile)
        self.plan_authority = repr(plans)
        self.relocations = {p.job.job_id: observe.RelocationState(p) for p in plans}
        self.derived_sources: dict[str, str] = {}
        super().__init__(profile.coordinator, conveyor, on_tick_settled=on_tick_settled)
        self.whole_places.update((p.target.owner_id, p.target) for p in plans)

    def run(self, horizon_tick: int, end_tick: int) -> CoordinatorOutcome:
        invariants.check_authority(self)
        if type(horizon_tick) is not int or any(
            s.plan.job.arrival_tick >= horizon_tick for s in self.relocations.values()
        ):
            raise ValueError("RELOCATION_ARRIVAL_OUTSIDE_HORIZON")
        base = super().run(horizon_tick, end_tick)
        return observe.outcome(base) if self.relocations else base

    def _initial_calendar(self) -> None:
        super()._initial_calendar()
        for key, state in self.relocations.items():
            heapq.heappush(self.pending, (state.plan.job.arrival_tick, "relocation_arrival", key))

    def _calendar_event(self, kind: str, key: str) -> None:
        if kind == "relocation_arrival":
            state = self.relocations[key]
            state.status = "waiting"
            self._relocation_event("relocation_arrived", state)
        else:
            super()._calendar_event(kind, key)

    def _finish_due(self) -> None:
        invariants.check_runtime(self, due=True)
        super()._finish_due()

    def _dispatch_external(self) -> None:
        invariants.check_authority(self)
        super()._dispatch_external()
        runtime.dispatch(self)

    def _place_free(self, owner_id: str) -> bool:
        return "relocation:place:" + owner_id not in self.leases and super()._place_free(owner_id)

    def _human_effect(self, order_id: str, kind: str) -> None:
        if order_id in self.relocations:
            runtime.completed(self, self.relocations[order_id], kind)
        else:
            super()._human_effect(order_id, kind)

    def _zero_step_done(self, worker: HumanState, step: HumanStep) -> None:
        if worker.order_id in self.relocations:
            runtime.completed(self, self.relocations[str(worker.order_id)], step.kind)
        else:
            super()._zero_step_done(worker, step)

    def _task_finished(self, worker: HumanState) -> None:
        if worker.task == "relocation":
            runtime.finish(self, worker)
        else:
            super()._task_finished(worker)

    def _emit(
        self,
        kind: str,
        order_id: str,
        *,
        worker: HumanState | None = None,
        delta: StockDelta | None = None,
    ) -> None:
        if order_id in self.relocations:
            self._relocation_event(kind, self.relocations[order_id], worker=worker, delta=delta)
        else:
            super()._emit(kind, order_id, worker=worker, delta=delta)

    def _relocation_event(
        self,
        kind: str,
        state: observe.RelocationState,
        *,
        worker: HumanState | None = None,
        delta: StockDelta | None = None,
        claim: StockClaim | None = None,
        released: str | None = None,
        resource: str | None = None,
    ) -> None:
        self.events.append(
            observe.RelocationEvent(
                len(self.events),
                self.tick,
                kind,
                state.plan.job.job_id,
                actor_id=state.plan.job.actor_id,
                operation=worker.operation if worker else None,
                delta=delta,
                inventory_claim=claim,
                released_claim_id=released,
                resource_id=resource,
                relocation=state.view(),
            )
        )

    def _complete(self) -> bool:
        return super()._complete() and all(
            s.returned_tick is not None for s in self.relocations.values()
        )

    def _settled_observation(self) -> None:
        if not self.relocations:
            super()._settled_observation()
            return
        if (
            self.business_tick is None
            and coordinator_observe.business_complete(self)
            and all(s.placed_tick is not None for s in self.relocations.values())
        ):
            self.business_tick = self.tick
        idle = coordinator_observe.resources_idle(self)
        if idle and not self.was_idle:
            self.resource_tick = self.tick
        elif not idle:
            self.resource_tick = None
        self.was_idle = idle
        LightFlowEngine._settled_observation(self)

    def _observe(self, tick: int) -> CoordinatorSnapshot:
        base = super()._observe(tick)
        return observe.snapshot(self, base) if self.relocations else base

    def _check(self) -> None:
        if self.relocations:
            invariants.check_world(self)
        else:
            super()._check()
