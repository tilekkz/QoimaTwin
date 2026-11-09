"""Intact SMALL/STANDARD outbound joins the existing single clock, actors and ledger."""

import heapq
from collections.abc import Callable

from app.v3.conveyor_models import ConveyorSource
from app.v3.light_flow_engine import LightFlowEngine
from app.v3.light_flow_models import FlowSnapshot
from app.v3.light_flow_plan import shipper_plan
from app.v3.light_flow_state import HumanState, HumanStep
from app.v3.receipt_flow_engine import ReceiptFlowEngine
from app.v3.receipt_flow_invariants import check_receipt_world
from app.v3.stock_claims import StockClaim
from app.v3.stock_ledger import StockLedger
from app.v3.stock_models import StockDelta
from app.v3.whole_flow_invariants import check_whole_world, shipped_resource
from app.v3.whole_flow_models import (
    WholeFlowEvent,
    WholeFlowOutcome,
    WholeFlowProfile,
    WholeFlowSnapshot,
)
from app.v3.whole_flow_plan import outbound_window, whole_plan
from app.v3.whole_flow_state import WholeState
from app.v3.whole_flow_validate import validate_whole_flow


def whole_snapshot(snapshot: FlowSnapshot) -> WholeFlowSnapshot:
    if not isinstance(snapshot, WholeFlowSnapshot):
        raise RuntimeError("Whole flow needs native snapshots")
    return snapshot


class WholeFlowEngine(ReceiptFlowEngine):
    def __init__(
        self,
        profile: WholeFlowProfile,
        conveyor: ConveyorSource,
        *,
        on_tick_settled: Callable[[FlowSnapshot, int], None] | None = None,
    ) -> None:
        ledger = self._validated_ledger(profile, conveyor)
        self.whole_profile = profile
        self.whole_orders = {
            o.job_id: WholeState(o) for o in sorted(profile.orders, key=lambda o: o.job_id)
        }
        self.whole_ports = {p.port_id: p for p in profile.ports}
        self.whole_places = {p.owner_id: p for p in profile.places}
        initial = {c.container_id: c.owner_id for c in profile.receipts.flow.stock.containers}
        initial.update((o.definition.hu_id, o.slot_owner_id) for o in profile.receipts.receipts)
        self.whole_sources = {o.job_id: initial[o.hu_id] for o in profile.orders}
        self.whole_wakes: set[tuple[int, str]] = set()
        self.parcel_ready: dict[str, int] = {}
        self._initialize_receipts(profile.receipts, conveyor, ledger, on_tick_settled)

    def _validated_ledger(self, profile: WholeFlowProfile, conveyor: ConveyorSource) -> StockLedger:
        return validate_whole_flow(profile, conveyor)

    def run(self, horizon_tick: int, end_tick: int) -> WholeFlowOutcome:
        if type(horizon_tick) is not int or any(
            o.spec.arrival_tick >= horizon_tick for o in self.whole_orders.values()
        ):
            raise ValueError("Every whole outbound arrival must be an integer within [0,H)")
        result = super().run(horizon_tick, end_tick)
        return WholeFlowOutcome(
            result.status,
            result.events,
            whole_snapshot(result.at_horizon),
            whole_snapshot(result.at_end),
            tuple(whole_snapshot(s) for s in result.checkpoints),
        )

    def _initial_calendar(self) -> None:
        super()._initial_calendar()
        for key, state in self.whole_orders.items():
            heapq.heappush(self.pending, (state.spec.arrival_tick, "whole_arrival", key))

    def _calendar_event(self, kind: str, key: str) -> None:
        if kind == "whole_arrival":
            self.whole_orders[key].status = "waiting"
            self._emit("whole_arrived", key)
        else:
            super()._calendar_event(kind, key)

    def _port_resource_id(self, order_id: str | None = None) -> str:
        profile = self._flow_for_order(order_id) if order_id is not None else self.profile
        return "port:" + profile.port.port_id

    def _relocate_material(self, transaction_id: str, container: str, owner: str) -> StockDelta:
        if self.owner_specs[owner].kind == "worker":
            return self.ledger.transfer_material_to_worker(
                transaction_id, self.ledger.revision, container, owner
            )
        return super()._relocate_material(transaction_id, container, owner)

    def _place_free(self, owner_id: str) -> bool:
        return "whole:place:" + owner_id not in self.leases and super()._place_free(owner_id)

    def _has_owner_capacity(self, owner_id: str) -> bool:
        return self._owner_usage(owner_id) < self.owner_specs[owner_id].capacity

    def _parcel_reservations(self, owner_id: str) -> int:
        key = self.leases.get(self._port_resource_id())
        return int(owner_id == self.profile.shipped_owner and key in self.orders)

    def _owner_usage(self, owner_id: str) -> int:
        reserved = sum(
            self.whole_ports[state.spec.port_id].shipped_owner == owner_id
            and state.port_reserved_tick is not None
            and state.shipped_tick is None
            for state in self.whole_orders.values()
        )
        occupied = sum(c.owner_id == owner_id for c in self.ledger.snapshot().containers)
        return occupied + reserved + self._parcel_reservations(owner_id)

    def _check_shipped_capacity(self) -> None:
        for owner in self.owner_specs.values():
            if owner.kind == "shipped" and self._owner_usage(owner.owner_id) > owner.capacity:
                raise RuntimeError("Shipped owner capacity exceeds placed and promised containers")

    def _stock_ready(self, state: WholeState) -> bool:
        receipt = self.future_hus.get(state.spec.hu_id)
        if receipt is not None and receipt.placed_tick is None:
            return False
        hu = self.ledger.contents(state.spec.hu_id).container
        return hu.owner_id == self.whole_sources[state.spec.job_id] and not any(
            c.container_id == state.spec.hu_id for c in self.ledger.claims
        )

    def _dispatch_shipment(self) -> None:
        candidates: list[tuple[int, int, str, bool]] = []
        for key in sorted(self.belt.at_output):
            if self.orders[key].status == "output":
                ready = self.parcel_ready.setdefault(key, self.tick)
                candidates.append((ready, self.orders[key].spec.arrival_tick, key, False))
        if self.tick < self.horizon:
            for key, state in self.whole_orders.items():
                if state.status == "waiting" and self._stock_ready(state):
                    if state.ready_tick is None:
                        state.ready_tick = self.tick
                    candidates.append((state.ready_tick, state.spec.arrival_tick, key, True))
        for _, _, key, whole in sorted(candidates):
            if whole:
                self._dispatch_whole(self.whole_orders[key])
            elif self.workers[self._flow_for_order(key).shipper_id].order_id is None:
                self._assign_parcel(key)

    def _assign_parcel(self, key: str) -> None:
        profile = self._flow_for_order(key)
        worker = self.workers[profile.shipper_id]
        if not self._worker_eligible(worker, "ship"):
            return
        order = self.orders[key]
        order.status = "collecting"
        self._assign(worker, order, "shipper", shipper_plan(profile, worker.spec, order.spec))

    def _dispatch_whole(self, state: WholeState) -> None:
        port = self.whole_ports[state.spec.port_id]
        buffers = sorted(k for k in port.buffer_ids if self._place_free(k))
        if not buffers:
            self._whole_wait(state, "buffer_busy")
            return
        workers = [
            self.workers[k]
            for k in sorted(port.shipper_ids)
            if self.workers[k].order_id is None and self._worker_eligible(self.workers[k], "ship")
        ]
        if not workers:
            self._whole_wait(state, "shipper_busy")
            return
        worker, buffer = workers[0], buffers[0]
        cargo = self.ledger.contents(state.spec.hu_id).container.recipe
        source = self.whole_places[self.whole_sources[state.spec.job_id]]
        steps = whole_plan(
            self.whole_profile,
            state.spec,
            cargo,
            source,
            self.whole_places[buffer],
            port,
            worker.spec,
        )
        self._admit_whole(state, worker, buffer, steps)

    def _admit_whole(
        self, state: WholeState, worker: HumanState, buffer: str, steps: list[HumanStep]
    ) -> None:
        key = state.spec.job_id
        if worker.node != worker.spec.home:
            raise RuntimeError("Whole shipper must begin at its actual home")
        resources = (
            "whole:worker:" + worker.spec.actor_id,
            "whole:place:" + buffer,
            "whole:hu:" + state.spec.hu_id,
        )
        if any(r in self.leases for r in resources):
            raise RuntimeError("Whole admission lost atomic resource ownership")
        claim = self.ledger.reserve_hu("whole:" + key, key, self.ledger.revision, state.spec.hu_id)
        state.actor_id, state.buffer_owner_id, state.admitted_tick = (
            worker.spec.actor_id,
            buffer,
            self.tick,
        )
        state.status, state.wait_reason = "approaching", None
        worker.order_id, worker.task, worker.steps, worker.waiting_since = (
            key,
            "whole",
            steps,
            self.tick,
        )
        self.leases.update((r, key) for r in resources)
        self._whole_event("inventory_claim_acquired", key, inventory_claim=claim)
        for resource in resources:
            self._whole_event("whole_resource_acquired", key, resource_id=resource)
        self._emit("whole_admitted", key, worker=worker)

    def _whole_wait(self, state: WholeState, reason: str | None) -> None:
        if state.wait_reason != reason:
            state.wait_reason = reason
            self._emit("whole_wait_changed", state.spec.job_id)

    def _step_gate(self, worker: HumanState, step: HumanStep) -> bool:
        if worker.task != "whole":
            return super()._step_gate(worker, step)
        state = self.whole_orders[str(worker.order_id)]
        if step.kind == "whole_pick_buffer":
            return self._reserve_port(state, worker)
        if step.kind == "whole_service":
            state.service_started_tick, state.status = self.tick, "service"
        return True

    def _reserve_port(self, state: WholeState, worker: HumanState) -> bool:
        port = self.whole_ports[state.spec.port_id]
        resource = "port:" + port.port_id
        if resource in self.leases or not self._has_owner_capacity(port.shipped_owner):
            self._whole_wait(state, "port_busy" if resource in self.leases else "shipped_capacity")
            return False
        approach = sum(s.duration for s in worker.steps[:2])
        duration = worker.steps[2].duration
        if not outbound_window(port, self.tick + approach, duration):
            self._port_wake(state, approach, duration)
            self._whole_wait(state, "service_window")
            return False
        key = state.spec.job_id
        state.port_reserved_tick = self.tick
        self._whole_wait(state, None)
        for name in (resource, shipped_resource(port, key)):
            self.leases[name] = key
            self._whole_event("whole_resource_acquired", key, resource_id=name)
        return True

    def _port_wake(self, state: WholeState, approach: int, duration: int) -> None:
        port = self.whole_ports[state.spec.port_id]
        candidates = [
            a - approach for a, b in port.windows if a - approach > self.tick and a + duration <= b
        ]
        if candidates:
            wake = min(candidates), state.spec.job_id
            if wake not in self.whole_wakes:
                self.whole_wakes.add(wake)
                heapq.heappush(self.pending, (wake[0], "whole_wake", wake[1]))

    def _human_effect(self, order_id: str, kind: str) -> None:
        if order_id not in self.whole_orders:
            super()._human_effect(order_id, kind)
            return
        state = self.whole_orders[order_id]
        if kind == "whole_pick_slot":
            self._move_whole(state, "actor:" + str(state.actor_id), "whole_picked")
            state.picked_tick, state.status = self.tick, "carrying"
        elif kind == "whole_place_buffer":
            self._move_whole(state, str(state.buffer_owner_id), "whole_buffered")
            state.buffered_tick, state.status = self.tick, "buffered"
        elif kind == "whole_pick_buffer":
            self._move_whole(state, "actor:" + str(state.actor_id), "whole_buffer_picked")
            state.buffer_picked_tick, state.status = self.tick, "carrying"
            self._release_whole(state, "whole:place:" + str(state.buffer_owner_id))
        elif kind == "whole_service":
            self._ship_whole(state)
        self._emit("whole_state_changed", order_id)

    def _move_whole(self, state: WholeState, owner: str, event: str) -> None:
        key = state.spec.job_id
        delta = self.ledger.transfer_whole_hu(
            key + ":" + event,
            self.ledger.revision,
            state.spec.hu_id,
            owner,
            claim_id="whole:" + key,
        )
        self._emit(event, key, delta=delta)

    def _ship_whole(self, state: WholeState) -> None:
        key, port = state.spec.job_id, self.whole_ports[state.spec.port_id]
        delta = self.ledger.ship_whole_hu(
            key + ":ship",
            self.ledger.revision,
            state.spec.hu_id,
            port.shipped_owner,
            claim_id="whole:" + key,
        )
        state.shipped_tick, state.status = self.tick, "returning"
        self._emit("whole_shipped", key, delta=delta)
        self._whole_event("inventory_claim_released", key, released_claim_id="whole:" + key)
        for resource in (
            "port:" + port.port_id,
            "whole:hu:" + state.spec.hu_id,
            shipped_resource(port, key),
        ):
            self._release_whole(state, resource)

    def _release_whole(self, state: WholeState, resource: str) -> None:
        if self.leases.get(resource) != state.spec.job_id:
            raise RuntimeError("Whole job released another owner's resource")
        del self.leases[resource]
        self._whole_event("whole_resource_released", state.spec.job_id, resource_id=resource)

    def _task_finished(self, worker: HumanState) -> None:
        if worker.task != "whole" or worker.steps:
            super()._task_finished(worker)
            return
        state = self.whole_orders[str(worker.order_id)]
        state.returned_tick, state.status = self.tick, "complete"
        self._release_whole(state, "whole:worker:" + str(state.actor_id))
        self._emit("whole_returned", state.spec.job_id, worker=worker)
        worker.stop_waiting(self.tick)
        worker.order_id, worker.task = None, "idle"

    def _emit(
        self,
        kind: str,
        order_id: str,
        *,
        worker: HumanState | None = None,
        delta: StockDelta | None = None,
    ) -> None:
        if order_id in self.whole_orders:
            self._whole_event(kind, order_id, worker=worker, delta=delta)
        else:
            super()._emit(kind, order_id, worker=worker, delta=delta)

    def _whole_event(
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
        state = self.whole_orders[order_id]
        self.events.append(
            WholeFlowEvent(
                len(self.events),
                self.tick,
                kind,
                order_id,
                actor_id=worker.spec.actor_id if worker else state.actor_id,
                operation=worker.operation if worker else None,
                delta=delta,
                inventory_claim=inventory_claim,
                released_claim_id=released_claim_id,
                resource_id=resource_id,
                whole_order=state.view(self.tick),
            )
        )

    def _complete(self) -> bool:
        return super()._complete() and all(
            s.status == "complete" for s in self.whole_orders.values()
        )

    def _check(self) -> None:
        LightFlowEngine._check(self)
        self._check_shipped_capacity()
        owners, claims = check_whole_world(
            self.whole_orders,
            self.whole_ports,
            self.whole_sources,
            self.workers,
            self.leases,
            self.ledger,
            self.tick,
            frozenset(
                s.offer.definition.hu_id for s in self.receipts.values() if s.placed_tick is None
            ),
        )
        additional_owners, additional_claims = self._additional_whole_ownership()
        if owners.keys() & additional_owners.keys() or claims & additional_claims:
            raise RuntimeError("Additional whole ownership overlaps existing physical work")
        owners.update(additional_owners)
        claims |= additional_claims
        check_receipt_world(
            self.receipt_profile,
            self.receipts,
            self.workers,
            self.leases,
            self.ledger,
            self.orders,
            self.pick_claims,
            self.tick,
            whole_owners=owners,
            whole_claims=claims,
        )

    def _additional_whole_ownership(self) -> tuple[dict[str, str], frozenset[str]]:
        """Native subclasses must validate their actual custody before returning authority."""
        return {}, frozenset()

    def _observe(self, tick: int) -> WholeFlowSnapshot:
        base = super()._observe(tick)
        return WholeFlowSnapshot(
            base.tick,
            base.stock,
            base.balance,
            base.workers,
            base.orders,
            base.leases,
            base.belt,
            base.last_seq,
            base.cart,
            base.inventory,
            base.receipts,
            tuple(s.view(tick) for s in self.whole_orders.values()),
        )
