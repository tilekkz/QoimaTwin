"""Receipt work extends the connected light calendar and its single physical ledger."""

import heapq
from collections.abc import Callable

from app.v3.conveyor_models import ConveyorSource
from app.v3.light_flow_engine import LightFlowEngine
from app.v3.light_flow_models import FlowOrder, FlowSnapshot
from app.v3.light_flow_state import HumanState, HumanStep, OrderState
from app.v3.receipt_flow_invariants import check_receipt_world
from app.v3.receipt_flow_models import (
    ReceiptFlowEvent,
    ReceiptFlowOutcome,
    ReceiptFlowProfile,
    ReceiptFlowSnapshot,
    ReceiptPort,
)
from app.v3.receipt_flow_plan import receipt_plan, receipt_window, window_wake
from app.v3.receipt_flow_state import ReceiptState
from app.v3.receipt_flow_validate import validate_receipt_flow
from app.v3.stock_claims import StockClaim
from app.v3.stock_commands import ReceiveHUCommand, TransferHUCommand
from app.v3.stock_ledger import StockLedger
from app.v3.stock_models import StockDelta


def native_snapshot(value: FlowSnapshot) -> ReceiptFlowSnapshot:
    if not isinstance(value, ReceiptFlowSnapshot):
        raise RuntimeError("Receipt flow requires native receipt snapshots")
    return value


class ReceiptFlowEngine(LightFlowEngine):
    def __init__(
        self,
        profile: ReceiptFlowProfile,
        conveyor: ConveyorSource,
        *,
        on_tick_settled: Callable[[FlowSnapshot, int], None] | None = None,
    ) -> None:
        ledger = validate_receipt_flow(profile, conveyor)
        self._initialize_receipts(profile, conveyor, ledger, on_tick_settled)

    def _initialize_receipts(
        self,
        profile: ReceiptFlowProfile,
        conveyor: ConveyorSource,
        ledger: StockLedger,
        on_tick_settled: Callable[[FlowSnapshot, int], None] | None,
    ) -> None:
        self.receipt_profile = profile
        self.receipts = {
            o.definition.receipt_id: ReceiptState(o)
            for o in sorted(profile.receipts, key=lambda o: o.definition.receipt_id)
        }
        self.receipt_ports = {p.port_id: p for p in profile.ports}
        self.receipt_places = {p.owner_id: p for p in profile.places}
        self.future_hus = {s.offer.definition.hu_id: s for s in self.receipts.values()}
        self.owner_specs = {o.owner_id: o for o in profile.flow.stock.owners + profile.flow.owners}
        self.pick_claims: dict[str, str] = {}
        self.receipt_wakes: set[tuple[int, str]] = set()
        self._initialize(profile.flow, conveyor, ledger, on_tick_settled)

    def run(self, horizon_tick: int, end_tick: int) -> ReceiptFlowOutcome:
        result = super().run(horizon_tick, end_tick)
        return ReceiptFlowOutcome(
            result.status,
            result.events,
            native_snapshot(result.at_horizon),
            native_snapshot(result.at_end),
            tuple(native_snapshot(s) for s in result.checkpoints),
        )

    def _initial_calendar(self) -> None:
        super()._initial_calendar()
        for key, state in self.receipts.items():
            if state.offer.arrival_tick < self.horizon:
                heapq.heappush(self.pending, (state.offer.arrival_tick, "receipt_arrival", key))

    def _calendar_event(self, kind: str, key: str) -> None:
        if kind == "receipt_arrival":
            self.receipts[key].status = "waiting"
            self._emit("receipt_arrived", key)
        else:
            super()._calendar_event(kind, key)

    def _dispatch_external(self) -> None:
        if self.tick >= self.horizon:
            return
        waiting = sorted(
            (s for s in self.receipts.values() if s.status == "waiting"),
            key=lambda s: (s.offer.arrival_tick, s.offer.definition.receipt_id),
        )
        for state in waiting:
            self._dispatch_receipt(state)

    def _place_free(self, owner_id: str) -> bool:
        return "receipt:place:" + owner_id not in self.leases and not any(
            c.owner_id == owner_id for c in self.ledger.snapshot().containers
        )

    def _dispatch_receipt(self, state: ReceiptState) -> None:
        port = self.receipt_ports[state.offer.port_id]
        if not self._place_free(state.offer.slot_owner_id):
            self._receipt_wait(state, "slot_busy")
            return
        buffers = sorted(key for key in port.buffer_ids if self._place_free(key))
        if not buffers:
            self._receipt_wait(state, "buffer_busy")
            return
        workers = [
            self.workers[key]
            for key in sorted(port.receiver_ids)
            if self.workers[key].order_id is None
            and self.workers[key].spec.available_tick <= self.tick
        ]
        if not workers:
            self._receipt_wait(state, "receiver_busy")
            return
        for worker in workers:
            steps = receipt_plan(
                self.receipt_profile,
                state.offer,
                port,
                self.receipt_places[buffers[0]],
                worker.spec,
            )
            if receipt_window(port, self.tick + steps[0].duration, port.service_tick, self.horizon):
                self._admit_receipt(state, worker, buffers[0], steps)
                return
            self._window_wake(state, port, steps[0].duration)
        self._receipt_wait(state, "service_window")

    def _window_wake(self, state: ReceiptState, port: ReceiptPort, approach: int) -> None:
        wake = window_wake(port, self.tick, approach, self.horizon)
        key = state.offer.definition.receipt_id
        if wake is not None and (wake, key) not in self.receipt_wakes:
            self.receipt_wakes.add((wake, key))
            heapq.heappush(self.pending, (wake, "receipt_wake", key))

    def _admit_receipt(
        self, state: ReceiptState, worker: HumanState, buffer: str, steps: list[HumanStep]
    ) -> None:
        if worker.node != worker.spec.home:
            raise RuntimeError("Receipt receiver did not return to its declared home")
        key = state.offer.definition.receipt_id
        resources = (
            "receipt:worker:" + worker.spec.actor_id,
            "receipt:place:" + buffer,
            "receipt:place:" + state.offer.slot_owner_id,
            "receipt:hu:" + state.offer.definition.hu_id,
        )
        if any(resource in self.leases for resource in resources):
            raise RuntimeError("Receipt atomic resource set changed during dispatch")
        state.actor_id, state.buffer_owner_id, state.admitted_tick = (
            worker.spec.actor_id,
            buffer,
            self.tick,
        )
        state.status, state.wait_reason = "approaching", None
        worker.order_id, worker.task, worker.steps = key, "receipt", steps
        worker.waiting_since = self.tick
        self.leases.update((resource, key) for resource in resources)
        for resource in resources:
            self._receipt_event("receipt_resource_acquired", key, resource_id=resource)
        self._emit("receipt_admitted", key, worker=worker)

    def _receipt_wait(self, state: ReceiptState, reason: str | None) -> None:
        if state.wait_reason != reason:
            state.wait_reason = reason
            self._emit("receipt_wait_changed", state.offer.definition.receipt_id)

    def _step_gate(self, worker: HumanState, step: HumanStep) -> bool:
        if worker.task != "receipt":
            return super()._step_gate(worker, step)
        if worker.order_id is None:
            raise RuntimeError("Receipt worker lacks its job")
        state = self.receipts[worker.order_id]
        if step.kind != "receipt_service":
            return True
        port = self.receipt_ports[state.offer.port_id]
        if not receipt_window(port, self.tick, step.duration, self.horizon):
            self._receipt_wait(state, "service_window")
            self._window_wake(state, port, 0)
            return False
        resource = "receipt:port:" + port.port_id
        if resource in self.leases:
            self._receipt_wait(state, "port_busy")
            return False
        self.leases[resource] = worker.order_id
        state.status = "service"
        self._receipt_wait(state, None)
        self._receipt_event("receipt_resource_acquired", worker.order_id, resource_id=resource)
        return True

    def _human_effect(self, order_id: str, kind: str) -> None:
        if order_id not in self.receipts:
            super()._human_effect(order_id, kind)
            return
        state = self.receipts[order_id]
        if kind == "receipt_approach":
            state.status = "awaiting_service"
        elif kind == "receipt_service":
            self._credit_receipt(state)
        elif kind == "receipt_place_buffer":
            self._move_receipt(state, state.buffer_owner_id, "receipt_buffered")
            state.status = "buffered"
        elif kind == "receipt_pick_buffer":
            self._move_receipt(state, "actor:" + str(state.actor_id), "receipt_buffer_picked")
            self._release_receipt(state, "receipt:place:" + str(state.buffer_owner_id))
            state.buffer_released = True
            state.status = "carrying"
        elif kind == "receipt_place_slot":
            self._putaway_receipt(state)
        self._emit("receipt_state_changed", order_id)

    def _credit_receipt(self, state: ReceiptState) -> None:
        key, definition = state.offer.definition.receipt_id, state.offer.definition
        delta = self.ledger.apply_once(
            ReceiveHUCommand(
                key + ":receive",
                self.ledger.revision,
                self.tick,
                definition,
                "actor:" + str(state.actor_id),
            )
        )
        state.credited_tick, state.status = self.tick, "carrying"
        self._emit("receipt_credited", key, delta=delta)
        claim = self.ledger.reserve_hu(
            "receipt:" + key, key, self.ledger.revision, definition.hu_id
        )
        self._receipt_event("inventory_claim_acquired", key, inventory_claim=claim)
        self._release_receipt(state, "receipt:port:" + state.offer.port_id)

    def _move_receipt(self, state: ReceiptState, owner_id: str | None, event: str) -> None:
        if owner_id is None:
            raise RuntimeError("Receipt movement lacks an actual destination")
        key = state.offer.definition.receipt_id
        delta = self.ledger.apply_once(
            TransferHUCommand(
                key + ":" + event,
                self.ledger.revision,
                self.tick,
                state.offer.definition.hu_id,
                owner_id,
                "receipt:" + key,
            )
        )
        self._emit(event, key, delta=delta)

    def _putaway_receipt(self, state: ReceiptState) -> None:
        key = state.offer.definition.receipt_id
        self._move_receipt(state, state.offer.slot_owner_id, "receipt_putaway")
        state.placed_tick, state.status = self.tick, "returning"
        self.ledger.release_claim("receipt:" + key, key)
        self._receipt_event("inventory_claim_released", key, released_claim_id="receipt:" + key)
        self._release_receipt(state, "receipt:place:" + state.offer.slot_owner_id)
        self._release_receipt(state, "receipt:hu:" + state.offer.definition.hu_id)

    def _release_receipt(self, state: ReceiptState, resource: str) -> None:
        key = state.offer.definition.receipt_id
        if self.leases.get(resource) != key:
            raise RuntimeError("Receipt released a resource owned by another job")
        del self.leases[resource]
        self._receipt_event("receipt_resource_released", key, resource_id=resource)

    def _task_finished(self, worker: HumanState) -> None:
        if worker.task != "receipt" or worker.steps:
            super()._task_finished(worker)
            return
        if worker.order_id is None:
            raise RuntimeError("Receipt return lacks its actual job")
        state = self.receipts[worker.order_id]
        state.returned_tick, state.status = self.tick, "complete"
        self._release_receipt(state, "receipt:worker:" + worker.spec.actor_id)
        self._emit("receipt_returned", worker.order_id, worker=worker)
        worker.stop_waiting(self.tick)
        worker.order_id, worker.task = None, "idle"

    def _order_ready(self, order: OrderState) -> bool:
        receipt = self.future_hus.get(order.spec.source_hu)
        if receipt is not None and receipt.placed_tick is None:
            return False
        contents = self.ledger.contents(order.spec.source_hu)
        if self.owner_specs[contents.container.owner_id].kind != "slot":
            return False
        ids = {p.unit_id for p in order.spec.carrier_placements}
        if not ids <= {u.token.unit_id for u in contents.units}:
            return False
        return not any(
            claim.container_id == order.spec.source_hu
            and (claim.whole_hu or bool(ids.intersection(claim.unit_ids)))
            for claim in self.ledger.claims
        )

    def _order_admitting(self, order: OrderState) -> None:
        key = order.spec.order_id
        claim = self.ledger.reserve_units(
            "pick:" + key,
            key,
            self.ledger.revision,
            order.spec.source_hu,
            tuple(p.unit_id for p in order.spec.carrier_placements),
        )
        self.pick_claims[key] = claim.claim_id
        self._receipt_event("inventory_claim_acquired", key, inventory_claim=claim)

    def _pick_stock(self, order: FlowOrder) -> StockDelta:
        claim = self.pick_claims[order.order_id]
        delta = self.ledger.pick(
            order.order_id + ":pick",
            self.ledger.revision,
            order.source_hu,
            order.carrier_id,
            order.carrier_placements,
            claim_id=claim,
        )
        del self.pick_claims[order.order_id]
        self._receipt_event("inventory_claim_released", order.order_id, released_claim_id=claim)
        return delta

    def _emit(
        self,
        kind: str,
        order_id: str,
        *,
        worker: HumanState | None = None,
        delta: StockDelta | None = None,
    ) -> None:
        if order_id in self.receipts:
            self._receipt_event(kind, order_id, worker=worker, delta=delta)
        else:
            super()._emit(kind, order_id, worker=worker, delta=delta)

    def _receipt_event(
        self,
        kind: str,
        order_id: str,
        *,
        worker: HumanState | None = None,
        delta: StockDelta | None = None,
        inventory_claim: StockClaim | None = None,
        released_claim_id: str | None = None,
        resource_id: str | None = None,
    ) -> None:
        state = self.receipts.get(order_id)
        self.events.append(
            ReceiptFlowEvent(
                len(self.events),
                self.tick,
                kind,
                order_id,
                actor_id=worker.spec.actor_id if worker else (state.actor_id if state else None),
                operation=worker.operation if worker else None,
                delta=delta,
                receipt=state.view(self.tick) if state else None,
                inventory_claim=inventory_claim,
                released_claim_id=released_claim_id,
                resource_id=resource_id,
            )
        )

    def _complete(self) -> bool:
        return super()._complete() and all(
            s.status == "complete" or s.offer.arrival_tick >= self.horizon
            for s in self.receipts.values()
        )

    def _check(self) -> None:
        super()._check()
        check_receipt_world(
            self.receipt_profile,
            self.receipts,
            self.workers,
            self.leases,
            self.ledger,
            self.orders,
            self.pick_claims,
            self.tick,
        )

    def _observe(self, tick: int) -> ReceiptFlowSnapshot:
        base = super()._observe(tick)
        return ReceiptFlowSnapshot(
            base.tick,
            base.stock,
            base.balance,
            base.workers,
            base.orders,
            base.leases,
            base.belt,
            base.last_seq,
            base.cart,
            self.ledger.inventory_snapshot(),
            tuple(s.view(tick) for s in self.receipts.values()),
        )
