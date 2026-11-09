"""B1 staffing runs on the existing connected whole/receipt/light physical world."""

import heapq
from collections.abc import Callable

from app.v3 import coordinator_observe as observe
from app.v3 import coordinator_packing as packing
from app.v3 import coordinator_roles as roles
from app.v3 import coordinator_units_runtime as unit_runtime
from app.v3 import coordinator_units_shipping as unit_shipping
from app.v3.belt_state import RunningCarrier
from app.v3.conveyor_models import ConveyorSource
from app.v3.coordinator_events import unit_event
from app.v3.coordinator_invariants import check_roles
from app.v3.coordinator_models import (
    CoordinatorEvent,
    CoordinatorOutcome,
    CoordinatorProfile,
    CoordinatorSnapshot,
    StaffViolation,
)
from app.v3.coordinator_packing_invariants import check_packing
from app.v3.coordinator_packing_models import PackingState, UnitContext
from app.v3.coordinator_state import RoleState
from app.v3.coordinator_units import order_views, preflight_units
from app.v3.coordinator_units_invariants import check_units
from app.v3.coordinator_units_state import UnitState
from app.v3.coordinator_units_validate import validate_resources
from app.v3.coordinator_validation import validate_horizon, validate_profile
from app.v3.light_flow_models import FlowCart, FlowProfile, FlowSnapshot
from app.v3.light_flow_state import HumanState, HumanStep, OrderState
from app.v3.staff_registry_values import ROLES
from app.v3.stock_ledger import StockLedger
from app.v3.stock_models import StockDelta
from app.v3.whole_flow_engine import WholeFlowEngine
from app.v3.whole_flow_models import WholeFlowProfile
from app.v3.whole_flow_validate import _validate_whole_flow


class CoordinatorEngine(WholeFlowEngine):
    def __init__(
        self,
        profile: CoordinatorProfile,
        conveyor: ConveyorSource,
        *,
        on_tick_settled: Callable[[FlowSnapshot, int], None] | None = None,
    ) -> None:
        validate_profile(profile)
        validate_resources(profile, conveyor)
        self.unit_profiles = order_views(profile)
        self.unit_states: dict[str, UnitState] = {}
        self.coordinator = profile
        self.role_states = {i.intent_id: RoleState(i) for i in profile.intents}
        self.role_stations = {s.station_id: s for s in profile.stations}
        self.capabilities = {w.actor_id: w for w in profile.registry.workers}
        self.primary_bindings = {
            b.station_id: b.primary_actor_id for b in profile.registry.station_bindings
        }
        self.station_bindings: dict[str, str] = {}
        self.unit_contexts: dict[str, UnitContext] = {}
        self.packing_states: dict[str, PackingState] = {}
        self.packing_waits: dict[str, str] = {}
        self.violations: list[StaffViolation] = []
        self.role_names = ROLES
        self.role_totals = dict.fromkeys((*ROLES, "transition", "unavailable"), 0)
        self.exposure_tick = 0
        self.business_tick: int | None = None
        self.resource_tick: int | None = 0
        self.was_idle = True
        super().__init__(profile.world, conveyor, on_tick_settled=on_tick_settled)

    def _validated_ledger(self, profile: WholeFlowProfile, conveyor: ConveyorSource) -> StockLedger:
        if self.coordinator.unit_resources is None:
            return super()._validated_ledger(profile, conveyor)
        return _validate_whole_flow(
            profile, conveyor, unit_validator=self._preflight_units, picker_home_at_cart=False
        )

    def _preflight_units(
        self,
        flow: FlowProfile,
        conveyor: ConveyorSource,
        ledger: StockLedger,
    ) -> None:
        preflight_units(self.unit_profiles, conveyor, ledger)

    def _flow_for_order(self, order_id: str) -> FlowProfile:
        if self.coordinator.unit_resources is not None:
            return self.unit_profiles[order_id]
        return self.profile

    def _cart_specs(self) -> tuple[FlowCart, ...]:
        resources = self.coordinator.unit_resources
        if resources is None:
            return super()._cart_specs()
        return tuple(c.cart for c in resources.carts)

    def _cart_resource(self, cart_id: str) -> str:
        return "cart:" + cart_id if self.coordinator.unit_resources is not None else "cart"

    def _dispatch_orders(self) -> None:
        if self.coordinator.unit_resources is None:
            super()._dispatch_orders()
            return
        if self.tick >= self.horizon:
            return
        waiting = sorted(
            (o for o in self.orders.values() if o.status == "waiting"),
            key=lambda o: (o.spec.arrival_tick, o.spec.order_id),
        )
        for order in waiting:
            profile = self._flow_for_order(order.spec.order_id)
            worker = self.workers[profile.picker_id]
            key = self._cart_resource(profile.cart.cart_id)
            if (
                not self._worker_eligible(worker, "pick")
                or key in self.leases
                or not self._order_ready(order)
            ):
                continue
            if (
                worker.node != worker.spec.home
                or self.carts[profile.cart.cart_id].node != profile.cart.home
            ):
                raise RuntimeError("UNIT_ADMISSION_REQUIRES_ACTUAL_RETURNED_ACTOR_AND_CART")
            self._order_admitting(order)
            order.status, order.admitted_tick = "picking", self.tick
            self.leases[key] = order.spec.order_id
            self._assign(
                worker, order, "picker", list(self.unit_states[order.spec.order_id].picker_steps)
            )
            self._emit("order_admitted", order.spec.order_id)

    def run(self, horizon_tick: int, end_tick: int) -> CoordinatorOutcome:
        validate_horizon(self.coordinator, horizon_tick, end_tick)
        result = super().run(horizon_tick, end_tick)
        snapshots = tuple(_native(s) for s in result.checkpoints)
        staffing = "violated" if self.violations else "valid" if self._roles_done() else "partial"
        return CoordinatorOutcome(
            result.status,
            result.events,
            _native(result.at_horizon),
            _native(result.at_end),
            snapshots,
            self.business_tick,
            self.resource_tick if observe.resources_idle(self) else None,
            result.at_end.tick,
            staffing,
            tuple(self.violations),
        )

    def _initial_calendar(self) -> None:
        super()._initial_calendar()
        if self.coordinator.unit_resources is not None:
            for port in self.coordinator.unit_resources.ports:
                for start, _ in port.port.windows:
                    if start:
                        heapq.heappush(self.pending, (start, "wake", port.port.port_id))
        heapq.heappush(self.pending, (self.horizon, "checkpoint", ""))
        for window in self.coordinator.registry.unavailability:
            for tick in (window.start_tick, window.end_tick):
                heapq.heappush(self.pending, (tick, "availability", window.actor_id))
        for state in self.role_states.values():
            for tick, kind in (
                (state.intent.request_tick, "role_request"),
                (state.intent.return_tick, "role_return"),
                (state.intent.restore_by_tick, "role_deadline"),
            ):
                heapq.heappush(self.pending, (tick, kind, state.intent.intent_id))

    def _finish_due(self) -> None:
        self.role_totals = observe.projected_exposure(self, self.tick)
        self.exposure_tick = self.tick
        due = []
        while self.pending and self.pending[0][0] == self.tick:
            due.append(heapq.heappop(self.pending))
        for _, kind, key in due:
            if kind == "human":
                self._calendar_event(kind, key)
        self.belt.finish_due(self.tick)
        for _, kind, key in due:
            if kind != "human":
                self._calendar_event(kind, key)

    def _calendar_event(self, kind: str, key: str) -> None:
        if kind == "availability":
            if not observe.available(self, key, self.tick) and not roles.clean(
                self, self.workers[key]
            ):
                self._violation(key, "PRIMARY_BREAK_NOT_CLEAN")
            self._staff_event("availability_changed", actor=key)
        elif kind == "role_request":
            state = self.role_states[key]
            state.status = "quiescing"
            self._staff_event("role_requested", state)
        elif kind == "role_deadline":
            state = self.role_states[key]
            if state.status not in {"restored", "rejected"}:
                self._violation(state.intent.actor_id, "RESTORATION_DEADLINE_MISSED", key)
                if state.status == "quiescing":
                    roles.reject(self, state, "ROLE_WINDOW_TOO_SHORT")
        elif kind != "role_return":
            super()._calendar_event(kind, key)

    def _dispatch_round(self) -> None:
        roles.dispatch(self)
        super()._dispatch_round()

    def _worker_eligible(self, worker: HumanState, role: str) -> bool:
        actor = worker.spec.actor_id
        state = observe.assignment(self, actor)
        if state is not None and state.status != "active":
            return False
        return (
            observe.available(self, actor, self.tick)
            and roles.clean(self, worker)
            and observe.effective_role(self, actor) == role
            and role in self.capabilities[actor].eligible_roles
        )

    def _human_effect(self, order_id: str, kind: str) -> None:
        if order_id not in self.role_states:
            super()._human_effect(order_id, kind)

    def _human_step_done(self, worker: HumanState, step: HumanStep) -> None:
        unit_runtime.completed(self, worker, step.kind)
        if self.coordinator.unit_resources is not None and step.kind == "shipping_service":
            unit_shipping.release(self, str(worker.order_id))

    def _step_gate(self, worker: HumanState, step: HumanStep) -> bool:
        allowed = super()._step_gate(worker, step)
        if (
            allowed
            and self.coordinator.unit_resources is not None
            and step.kind == "shipping_service"
        ):
            unit_shipping.reserve(self, str(worker.order_id))
        return allowed

    def _parcel_reservations(self, owner_id: str) -> int:
        if self.coordinator.unit_resources is None:
            return super()._parcel_reservations(owner_id)
        return unit_shipping.parcel_reservations(self, owner_id)

    def _assign_parcel(self, key: str) -> None:
        super()._assign_parcel(key)
        if key in self.unit_states:
            worker = self.workers[self._flow_for_order(key).shipper_id]
            if worker.order_id == key and worker.task == "shipper":
                self.unit_states[key].shipper_steps = tuple(worker.steps)

    def _zero_step_done(self, worker: HumanState, step: HumanStep) -> None:
        unit_runtime.completed(self, worker, step.kind)

    def _task_finished(self, worker: HumanState) -> None:
        if worker.order_id in self.role_states:
            roles.finished(self, worker)
        elif worker.order_id in self.packing_states and worker.task in {
            "packer_approach",
            "packer_return",
        }:
            packing.task_finished(self, worker)
        elif not unit_runtime.finish_picker(self, worker) and not unit_runtime.finish_shipper(
            self, worker
        ):
            super()._task_finished(worker)

    def _emit(
        self,
        kind: str,
        order_id: str,
        *,
        worker: HumanState | None = None,
        delta: StockDelta | None = None,
    ) -> None:
        if order_id in self.role_states:
            self._staff_event(kind, self.role_states[order_id], worker=worker)
        elif order_id in self.unit_contexts:
            unit_event(self, kind, order_id, worker=worker, delta=delta)
        else:
            super()._emit(kind, order_id, worker=worker, delta=delta)

    def _order_admitting(self, order: OrderState) -> None:
        super()._order_admitting(order)
        packing.bind_order(self, order)
        unit_runtime.admit(self, order)

    def station_ready(self, state: RunningCarrier, stage: str) -> bool:
        return packing.ready(self, state, stage)

    def station_started(self, state: RunningCarrier, stage: str) -> None:
        packing.started(self, state, stage)

    def station_finished(self, state: RunningCarrier, stage: str) -> None:
        packing.finished(self, state, stage)

    def _packing_event(
        self, kind: str, state: PackingState, *, resources: tuple[str, ...] = ()
    ) -> None:
        unit_event(
            self, kind, state.order_id, worker=self.workers[state.actor_id], resources=resources
        )

    def _staff_event(
        self,
        kind: str,
        state: RoleState | None = None,
        *,
        worker: HumanState | None = None,
        actor: str | None = None,
    ) -> None:
        key = state.intent.intent_id if state else "availability:" + str(actor)
        self.events.append(
            CoordinatorEvent(
                len(self.events),
                self.tick,
                kind,
                key,
                actor_id=worker.spec.actor_id
                if worker
                else state.intent.actor_id
                if state
                else actor,
                operation=worker.operation if worker else None,
                work_kind="role_intent" if state else "availability",
                role_view=state.view() if state else None,
            )
        )

    def _violation(self, actor: str, reason: str, intent: str | None = None) -> None:
        value = StaffViolation(self.tick, actor, reason, intent)
        if value not in self.violations:
            self.violations.append(value)

    def _roles_done(self) -> bool:
        return all(s.status in {"restored", "rejected"} for s in self.role_states.values())

    def _complete(self) -> bool:
        return super()._complete() and self._roles_done()

    def _may_stop(self) -> bool:
        return self.tick >= self.horizon

    def _settled_observation(self) -> None:
        if self.business_tick is None and observe.business_complete(self):
            self.business_tick = self.tick
        idle = observe.resources_idle(self)
        if idle and not self.was_idle:
            self.resource_tick = self.tick
        elif not idle:
            self.resource_tick = None
        self.was_idle = idle
        super()._settled_observation()

    def _observe(self, tick: int) -> CoordinatorSnapshot:
        return observe.snapshot(self, super()._observe(tick), tick)

    def _check(self) -> None:
        super()._check()
        check_roles(self)
        check_packing(self)
        check_units(self)
        if self.coordinator.unit_resources is not None:
            unit_shipping.check_shipping(self)


def _native(value: FlowSnapshot) -> CoordinatorSnapshot:
    if not isinstance(value, CoordinatorSnapshot):
        raise RuntimeError("COORDINATOR_SNAPSHOT_REQUIRED")
    return value
