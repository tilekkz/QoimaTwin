"""One settled microsecond clock owns humans, physical belt work and stock effects."""

import heapq
from collections.abc import Callable
from dataclasses import replace

from app.v3.belt_models import BeltEvent, BeltJob
from app.v3.belt_state import RunningCarrier
from app.v3.conveyor_models import ConveyorPayload, ConveyorSource
from app.v3.light_flow_belt import FlowBelt
from app.v3.light_flow_models import (
    FlowCartView,
    FlowEvent,
    FlowOperation,
    FlowOrder,
    FlowOrderView,
    FlowOutcome,
    FlowProfile,
    FlowSnapshot,
)
from app.v3.light_flow_plan import picker_plan, shipper_plan, travel
from app.v3.light_flow_state import HumanState, HumanStep, OrderState
from app.v3.light_flow_validate import validate
from app.v3.stock_ledger import StockLedger
from app.v3.stock_models import StockDelta


class LightFlowEngine:
    def __init__(
        self,
        profile: FlowProfile,
        conveyor: ConveyorSource,
        *,
        on_tick_settled: Callable[[FlowSnapshot, int], None] | None = None,
    ) -> None:
        self._initialize(profile, conveyor, validate(profile, conveyor), on_tick_settled)

    def _initialize(
        self,
        profile: FlowProfile,
        conveyor: ConveyorSource,
        ledger: StockLedger,
        on_tick_settled: Callable[[FlowSnapshot, int], None] | None,
    ) -> None:
        self.profile = profile
        self.ledger = ledger
        self.workers = {a.actor_id: HumanState(a, a.home) for a in profile.actors}
        self.orders = {
            o.order_id: OrderState(o) for o in sorted(profile.orders, key=lambda o: o.order_id)
        }
        self.belt = FlowBelt(conveyor, self, profile.times.clear)
        self.events: list[FlowEvent] = []
        self.pending: list[tuple[int, str, str]] = []
        self.leases: dict[str, str] = {}
        self.tick, self.horizon, self.end_cap = 0, 0, 0
        self.cart_node: str | None = profile.cart.home
        self.cart_operation: FlowOperation | None = None
        self.checkpoints: list[FlowSnapshot] = []
        self.on_tick_settled = on_tick_settled
        self.used = False

    def run(self, horizon_tick: int, end_tick: int) -> FlowOutcome:
        if self.used or type(horizon_tick) is not int or type(end_tick) is not int:
            raise ValueError("Single-use engine with integer clocks required")
        if not 0 < horizon_tick <= end_tick or any(
            o.spec.arrival_tick >= horizon_tick for o in self.orders.values()
        ):
            raise ValueError("Require positive H<=end and every offered arrival<H")
        self.used, self.horizon, self.end_cap = True, horizon_tick, end_tick
        self._initial_calendar()
        at_horizon: FlowSnapshot | None = None
        while self.pending or self.belt.pending:
            next_tick = min(
                self.pending[0][0] if self.pending else end_tick + 1,
                self.belt.pending[0][0] if self.belt.pending else end_tick + 1,
            )
            if at_horizon is None and horizon_tick < next_tick:
                at_horizon = self._observe(horizon_tick)
            if next_tick > end_tick:
                break
            self.tick = self.belt.tick = next_tick
            self._settle()
            self._settled_observation()
            if next_tick == horizon_tick:
                at_horizon = self._observe(horizon_tick)
            if self._complete():
                break
        complete = self._complete()
        at_end = self._observe(self.tick if complete else end_tick)
        if not self.checkpoints or self.checkpoints[-1].tick != at_end.tick:
            self.checkpoints.append(at_end)
        return FlowOutcome(
            "complete" if complete else "partial",
            tuple(self.events),
            at_horizon or self._observe(horizon_tick),
            at_end,
            tuple(self.checkpoints),
        )

    def _initial_calendar(self) -> None:
        for tick in range(0, self.end_cap + 1, 30_000_000):
            heapq.heappush(self.pending, (tick, "checkpoint", ""))
        for order in self.orders.values():
            heapq.heappush(self.pending, (order.spec.arrival_tick, "arrival", order.spec.order_id))
        for actor in self.workers.values():
            if actor.spec.available_tick:
                heapq.heappush(
                    self.pending, (actor.spec.available_tick, "wake", actor.spec.actor_id)
                )
        for start, _ in self.profile.port.windows:
            if start:
                heapq.heappush(self.pending, (start, "wake", "port"))

    def _settled_observation(self) -> None:
        if self.tick % 30_000_000 and self.on_tick_settled is None:
            return
        value = self._observe(self.tick)
        if self.tick % 30_000_000 == 0:
            self.checkpoints.append(value)
        if self.on_tick_settled is not None:
            self.on_tick_settled(value, value.last_seq)

    def _settle(self) -> None:
        while self.pending and self.pending[0][0] == self.tick:
            _, kind, key = heapq.heappop(self.pending)
            self._calendar_event(kind, key)
        self.belt.finish_due(self.tick)
        for _ in range(100):
            previous = len(self.events), len(self.pending), len(self.belt.pending)
            self._dispatch_external()
            self._dispatch_orders()
            self._dispatch_shipment()
            for worker in sorted(self.workers.values(), key=lambda w: w.spec.actor_id):
                self._start_step(worker)
            self.belt.dispatch(self.tick)
            if previous == (len(self.events), len(self.pending), len(self.belt.pending)):
                break
        else:
            raise RuntimeError("Zero-time dispatch failed to settle")
        self._check()

    def _calendar_event(self, kind: str, key: str) -> None:
        if kind == "human":
            self._human_done(self.workers[key])
        elif kind == "arrival":
            self.orders[key].status = "waiting"
            self._emit("order_arrived", key)

    def _dispatch_external(self) -> None:
        """Additional native work shares this calendar; legacy profiles have none."""

    def _order_ready(self, order: OrderState) -> bool:
        return True

    def _order_admitting(self, order: OrderState) -> None:
        """Native variants may reserve the exact contents before paid picking."""

    def _dispatch_orders(self) -> None:
        worker = self.workers[self.profile.picker_id]
        if (
            self.tick >= self.horizon
            or worker.order_id is not None
            or self.tick < worker.spec.available_tick
        ):
            return
        if "cart" in self.leases:
            return
        waiting = sorted(
            (o for o in self.orders.values() if o.status == "waiting"),
            key=lambda o: (o.spec.arrival_tick, o.spec.order_id),
        )
        if waiting and self._order_ready(waiting[0]):
            order = waiting[0]
            self._order_admitting(order)
            order.status, order.admitted_tick = "picking", self.tick
            self.leases["cart"] = order.spec.order_id
            self._assign(
                worker, order, "picker", picker_plan(self.profile, worker.spec, order.spec)
            )
            self._emit("order_admitted", order.spec.order_id)

    def _dispatch_shipment(self) -> None:
        worker = self.workers[self.profile.shipper_id]
        if worker.order_id is not None or self.tick < worker.spec.available_tick:
            return
        waiting = sorted(o for o in self.belt.at_output if self.orders[o].status == "output")
        if waiting:
            order = self.orders[waiting[0]]
            order.status = "collecting"
            self._assign(
                worker, order, "shipper", shipper_plan(self.profile, worker.spec, order.spec)
            )

    def _assign(
        self, worker: HumanState, order: OrderState, task: str, steps: list[HumanStep]
    ) -> None:
        worker.order_id, worker.task, worker.steps = order.spec.order_id, task, steps
        worker.waiting_since = self.tick
        self._emit("actor_assigned", order.spec.order_id, worker=worker)

    def _start_step(self, worker: HumanState) -> None:
        if (
            worker.operation is not None
            or not worker.steps
            or self.tick < worker.spec.available_tick
        ):
            return
        step = worker.steps[0]
        if step.duration == 0:
            if worker.node != step.target:
                raise RuntimeError("Zero-duration spatial jump")
            worker.steps.pop(0)
            self._task_finished(worker)
            self._start_step(worker)
            return
        if not self._step_gate(worker, step):
            return
        self._start_operation(worker, step)
        heapq.heappush(self.pending, (self.tick + step.duration, "human", worker.spec.actor_id))

    def _start_operation(self, worker: HumanState, step: HumanStep) -> None:
        if worker.node is None or worker.order_id is None:
            raise RuntimeError("Human operation has no current location/order")
        if step.route is not None and step.route.node_ids[0] != worker.node:
            raise RuntimeError("Human route teleports between anchors")
        if step.route is None and step.target != worker.node:
            raise RuntimeError("Service operation changes spatial anchor")
        worker.stop_waiting(self.tick)
        worker.operation = FlowOperation(
            step.kind,
            worker.order_id,
            self.tick,
            self.tick + step.duration,
            worker.node,
            step.target,
            step.route,
            step.carrying_id,
            step.cart_id,
        )
        if step.cart_id is not None:
            if worker.node != self.cart_node:
                raise RuntimeError("Paid cart operation starts away from the physical cart")
            self.cart_operation = worker.operation
            if step.route is not None:
                self.cart_node = None
        if step.route is not None:
            worker.node = None
        self._emit("operation_started", worker.order_id, worker=worker)

    def _step_gate(self, worker: HumanState, step: HumanStep) -> bool:
        assert worker.order_id is not None
        if step.kind == "deposit":
            return self.belt.reserve_intake(
                self._belt_job(worker.order_id, self.tick + step.duration)
            )
        if step.kind == "shipping_service":
            fits = any(
                start <= self.tick < end and self.tick + step.duration <= end
                for start, end in self.profile.port.windows
            )
            if (
                not fits
                or "port" in self.leases
                or not self._has_owner_capacity(self.profile.shipped_owner)
            ):
                return False
            self.leases["port"] = worker.order_id
        return True

    def _human_done(self, worker: HumanState) -> None:
        self._finish_operation(worker)
        step = worker.steps.pop(0)
        assert worker.order_id is not None
        self._human_effect(worker.order_id, step.kind)
        worker.waiting_since = self.tick
        self._task_finished(worker)

    def _finish_operation(self, worker: HumanState) -> None:
        operation = worker.operation
        if operation is None or operation.planned_end_tick != self.tick:
            raise RuntimeError("Mismatched paid human completion")
        self._emit("operation_completed", operation.order_id, worker=worker)
        worker.closed_paid += self.tick - operation.start_tick
        worker.node, worker.operation = operation.target_node, None
        if operation.cart_id is not None:
            self.cart_node, self.cart_operation = operation.target_node, None

    def _task_finished(self, worker: HumanState) -> None:
        if worker.steps:
            return
        if worker.task == "packer_approach":
            worker.task = "station"
            return
        if worker.task == "picker":
            del self.leases["cart"]
        worker.stop_waiting(self.tick)
        worker.order_id, worker.task = None, "idle"

    def _human_effect(self, order_id: str, kind: str) -> None:
        order, p = self.orders[order_id].spec, self.profile
        if kind in {"attach", "source_attach"}:
            self._relocate(
                "carrier_attached" if kind == "attach" else "carrier_reattached",
                order_id,
                order.carrier_id,
                p.cart.owner_id,
            )
        elif kind == "pick":
            delta = self._pick_stock(order)
            self._emit("picked", order_id, delta=delta)
        elif kind in {"detach", "source_detach"}:
            self._relocate(
                "carrier_detached" if kind == "detach" else "source_carrier_detached",
                order_id,
                order.carrier_id,
                "actor:" + p.picker_id,
            )
        elif kind == "deposit":
            self._relocate("intake_handoff", order_id, order.carrier_id, "belt:" + order_id)
            self.orders[order_id].status = "belt"
            self.belt.admit(self._belt_job(order_id, self.tick), self.tick)
        elif kind == "pickup_package":
            self._relocate("output_collected", order_id, order.package_id, "actor:" + p.shipper_id)
            self.belt.collect(order_id)
        elif kind == "shipping_service":
            delta = self.ledger.ship(
                order_id + ":ship", self.ledger.revision, order.package_id, p.shipped_owner
            )
            self.orders[order_id].status, self.orders[order_id].shipped_tick = "shipped", self.tick
            del self.leases["port"]
            self._emit("shipped", order_id, delta=delta)

    def _pick_stock(self, order: FlowOrder) -> StockDelta:
        return self.ledger.pick(
            order.order_id + ":pick",
            self.ledger.revision,
            order.source_hu,
            order.carrier_id,
            order.carrier_placements,
        )

    def station_ready(self, state: RunningCarrier, stage: str) -> bool:
        worker, order = self.workers[self.profile.packer_id], self.orders[state.job.job_id]
        if worker.order_id is None and self.tick >= worker.spec.available_tick:
            step = travel(
                self.profile,
                worker.spec,
                worker.spec.home,
                self.profile.station.node,
                "travel_empty",
            )
            self._assign(worker, order, "packer_approach", [step])
        if worker.order_id != order.spec.order_id or worker.operation is not None or worker.steps:
            return False
        if stage == "clear":
            return self.belt.reserve_replacement(
                state, self._payload(order.spec.package_id, order.spec.order_id, "sealed_parcel")
            )
        return self._has_owner_capacity(self.profile.station.empty_owner)

    def station_started(self, state: RunningCarrier, stage: str) -> None:
        worker, order = self.workers[self.profile.packer_id], self.orders[state.job.job_id]
        if stage == "pack":
            self._relocate(
                "package_prepared",
                order.spec.order_id,
                order.spec.package_id,
                self.profile.station.bench_owner,
            )
        duration = self.profile.times.pack if stage == "pack" else self.profile.times.clear
        self._start_operation(worker, HumanStep(stage, self.profile.station.node, duration))
        order.status = "packing"

    def station_finished(self, state: RunningCarrier, stage: str) -> None:
        worker, order = self.workers[self.profile.packer_id], self.orders[state.job.job_id].spec
        self._finish_operation(worker)
        worker.waiting_since = self.tick
        if stage == "pack":
            delta = self.ledger.pack(
                order.order_id + ":pack",
                self.ledger.revision,
                order.carrier_id,
                order.package_id,
                order.package_placements,
                order_id=order.order_id,
            )
            self._emit("packed", order.order_id, delta=delta)
            state.job = replace(
                state.job, payload=self._payload(order.carrier_id, order.order_id, "order_tote")
            )
            self.belt._emit(state, "contents_changed")
        else:
            self._relocate(
                "empty_carrier_cleared",
                order.order_id,
                order.carrier_id,
                self.profile.station.empty_owner,
            )
            self._relocate(
                "parcel_loaded", order.order_id, order.package_id, "belt:" + order.order_id
            )
            self.belt.replace_payload(
                state, self._payload(order.package_id, order.order_id, "sealed_parcel")
            )
            step = travel(
                self.profile, worker.spec, self.profile.station.node, worker.spec.home, "return"
            )
            self._assign(worker, self.orders[order.order_id], "packer_return", [step])
            self.orders[order.order_id].status = "belt_return"

    def output_ready(self, state: RunningCarrier) -> None:
        self.orders[state.job.job_id].status = "output"
        self._emit("output_ready", state.job.job_id)

    def belt_event(self, event: BeltEvent) -> None:
        self.events.append(
            FlowEvent(
                len(self.events), self.tick, "belt:" + event.kind, event.job_id, belt_event=event
            )
        )

    def _belt_job(self, order_id: str, arrival: int) -> BeltJob:
        order = self.orders[order_id].spec
        return BeltJob(
            order_id,
            order.carrier_id,
            self._payload(order.carrier_id, order_id, "order_tote"),
            arrival,
            self.profile.belt_route,
            self.profile.station.station_id,
            self.profile.times.pack,
        )

    def _payload(self, identity: str, order_id: str, kind: str) -> ConveyorPayload:
        view = self.ledger.contents(identity)
        return ConveyorPayload(
            identity,
            kind,
            view.container.recipe.outer,
            view.gross_mass_kg,
            "upright_xyz",
            order_id,
            view.container.recipe.provenance,
        )

    def _relocate(self, kind: str, order_id: str, container: str, owner: str) -> None:
        delta = self.ledger.relocate(order_id + ":" + kind, self.ledger.revision, container, owner)
        self._emit(kind, order_id, delta=delta)

    def _emit(
        self,
        kind: str,
        order_id: str,
        *,
        worker: HumanState | None = None,
        delta: StockDelta | None = None,
    ) -> None:
        self.events.append(
            FlowEvent(
                len(self.events),
                self.tick,
                kind,
                order_id,
                worker.spec.actor_id if worker else None,
                worker.operation if worker else None,
                delta,
            )
        )

    def _has_owner_capacity(self, owner_id: str) -> bool:
        capacity = next(o.capacity for o in self.profile.owners if o.owner_id == owner_id)
        return sum(c.owner_id == owner_id for c in self.ledger.snapshot().containers) < capacity

    def _complete(self) -> bool:
        return (
            all(o.status == "shipped" for o in self.orders.values())
            and all(w.order_id is None for w in self.workers.values())
            and not self.leases
            and all(s.complete for s in self.belt.states)
        )

    def _check(self) -> None:
        self.ledger.check_invariants()
        self.belt._observe(self.tick)
        for worker in self.workers.values():
            if worker.operation is not None and worker.operation.planned_end_tick <= self.tick:
                raise RuntimeError("Unsettled human completion")
        for state in self.belt.states:
            if not state.complete:
                view = self.ledger.contents(state.job.payload.payload_id)
                if (
                    view.container.owner_id != "belt:" + state.job.job_id
                    or view.gross_mass_kg != state.job.payload.gross_mass_kg
                ):
                    raise RuntimeError("Belt and stock physical ownership/mass disagree")

    def _observe(self, tick: int) -> FlowSnapshot:
        return FlowSnapshot(
            tick,
            self.ledger.snapshot(),
            self.ledger.balance(),
            tuple(w.view(tick) for _, w in sorted(self.workers.items())),
            tuple(
                FlowOrderView(o.spec.order_id, o.status, o.admitted_tick, o.shipped_tick)
                for o in self.orders.values()
            ),
            tuple(sorted(self.leases.items())) + tuple(sorted(self.belt.external.items())),
            self.belt._observe(tick),
            len(self.events) - 1,
            FlowCartView(
                self.profile.cart.cart_id,
                self.cart_node,
                self.cart_operation,
                self.leases.get("cart"),
            ),
        )
