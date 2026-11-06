"""Receiving and putaway to the west ground reserve (spec 01 §6, ADR 0009 A18-A20).

A receipt that finds a free receiving position crosses the warehouse boundary and enters the ledger.
Otherwise it waits in an external FIFO outside the ledger. A pallet holds its receiving position
from acceptance until the inbound forklift picks it up; receivers serve pallets in place. The
inbound forklift reserves a reserve-staging place before it drives; a full reserve blocks putaway,
then receiving, then acceptance.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from functools import partial
from typing import TYPE_CHECKING

from app.contracts.base import exact
from app.contracts.scenario import Receipt
from app.inventory.ledger import Location, LocKind
from app.simulation.recorder import ActorState, Vec3
from app.simulation.scheduler import Phase

if TYPE_CHECKING:
    from app.simulation.context import SimContext
    from app.simulation.engine import Engine

HOME, PICK, DROP = "FI_HOME", "FI_PICK", "FI_DROP"


class InboundState(StrEnum):
    WAITING = "WAITING"
    IN_SERVICE = "IN_SERVICE"
    PROCESSED = "PROCESSED"
    CLAIMED = "CLAIMED"


@dataclass(slots=True)
class InboundPallet:
    receipt: Receipt
    pallet_id: str
    state: InboundState = InboundState.WAITING


@dataclass(slots=True)
class Receiver:
    actor_id: str
    pos: Vec3
    busy: bool = False


class Receiving:
    def __init__(self, ctx: SimContext, engine: Engine) -> None:
        self.ctx = ctx
        self.engine = engine
        self.external: deque[Receipt] = deque()
        self.area: list[InboundPallet] = []
        self.receivers = [
            Receiver(a.actor_id, a.initial_pos) for a in ctx.inputs.actors.by_role("receiver")
        ]
        vehicle = next(v for v in ctx.inputs.actors.vehicles if v.graph_id == "inbound")
        self.driver_id = vehicle.driver_actor_id
        self.forklift_busy = False
        self.staging_used = 0
        self.putaway_ticks: list[int] = []

    # ----- boundary -----
    def on_arrival(self, receipt: Receipt) -> None:
        self.external.append(receipt)
        self.ctx.request_dispatch()

    def admit(self) -> bool:
        changed = False
        while self.external and len(self.area) < self.ctx.config.receiving_queue_capacity:
            receipt = self.external.popleft()
            pallet = InboundPallet(receipt, f"IN_{receipt.receipt_id}")
            self.area.append(pallet)
            self.ctx.ledger.accept_receipt(
                receipt.sku_id, receipt.receipt_id, self._area_location(pallet), receipt.quantity
            )
            self.ctx.recorder.emit(
                self.ctx.now,
                Phase.DISPATCH,
                "receipt_accepted",
                receipt.receipt_id,
                receipt_id=receipt.receipt_id,
                pallet_id=pallet.pallet_id,
                sku_id=receipt.sku_id,
                quantity=receipt.quantity,
                ledger_to=str(LocKind.RECEIVING),
            )
            changed = True
        return changed

    @staticmethod
    def _area_location(pallet: InboundPallet) -> Location:
        return Location(LocKind.RECEIVING, pallet.pallet_id)

    # ----- receivers -----
    def start_services(self) -> bool:
        changed = False
        for receiver in self.receivers:
            pallet = next((p for p in self.area if p.state is InboundState.WAITING), None)
            if receiver.busy or pallet is None:
                continue
            receiver.busy = True
            pallet.state = InboundState.IN_SERVICE
            end = self.ctx.now + self.ctx.ticks(exact(self.ctx.config.receive_service_s))
            self.ctx.recorder.act(
                receiver.actor_id,
                ActorState.BUSY_SERVICE,
                "receive",
                self.ctx.now,
                end,
                pallet.pallet_id,
                pos=receiver.pos,
            )
            self.ctx.sched.schedule(
                end,
                Phase.COMPLETION,
                partial(self._processed, receiver, pallet),
                key=(receiver.actor_id,),
            )
            changed = True
        return changed

    def _processed(self, receiver: Receiver, pallet: InboundPallet) -> None:
        receiver.busy = False
        pallet.state = InboundState.PROCESSED
        r = pallet.receipt
        self.ctx.recorder.emit(
            self.ctx.now,
            Phase.COMPLETION,
            "receipt_processed",
            r.receipt_id,
            receipt_id=r.receipt_id,
            pallet_id=pallet.pallet_id,
            sku_id=r.sku_id,
            quantity=r.quantity,
            actor_id=receiver.actor_id,
        )
        self.ctx.request_dispatch()

    # ----- inbound forklift -----
    def assign_putaway(self) -> bool:
        if self.forklift_busy or self.staging_used >= self.ctx.config.reserve_staging_capacity:
            return False
        pallet = next((p for p in self.area if p.state is InboundState.PROCESSED), None)
        if pallet is None:
            return False
        pallet.state = InboundState.CLAIMED
        self.forklift_busy = True
        self.staging_used += 1
        arrive = self._drive(HOME, PICK, self.ctx.now, "to_pickup", pallet.pallet_id)
        end = self._service(arrive, self.ctx.config.forklift_pickup_s, "pickup", pallet, PICK)
        self.ctx.sched.schedule(
            end, Phase.COMPLETION, lambda: self._picked_up(pallet), key=(self.driver_id,)
        )
        return True

    def _picked_up(self, pallet: InboundPallet) -> None:
        vehicle = Location(LocKind.INBOUND_VEHICLE, self.driver_id)
        self.ctx.ledger.transfer_location(self._area_location(pallet), vehicle)
        self.area.remove(pallet)
        arrive = self._drive(PICK, DROP, self.ctx.now, "to_reserve", pallet.pallet_id)
        end = self._service(arrive, self.ctx.config.forklift_drop_s, "putaway", pallet, DROP)
        self.ctx.sched.schedule(
            end, Phase.COMPLETION, lambda: self._stored(pallet), key=(self.driver_id,)
        )
        self.ctx.request_dispatch()

    def _stored(self, pallet: InboundPallet) -> None:
        ctx = self.ctx
        vehicle = Location(LocKind.INBOUND_VEHICLE, self.driver_id)
        ctx.ledger.transfer_location(vehicle, Location(LocKind.RESERVE_STAGING, pallet.pallet_id))
        r = pallet.receipt
        ctx.recorder.emit(
            ctx.now,
            Phase.COMPLETION,
            "pallet_putaway",
            r.receipt_id,
            receipt_id=r.receipt_id,
            pallet_id=pallet.pallet_id,
            sku_id=r.sku_id,
            quantity=r.quantity,
            actor_id=self.driver_id,
            ledger_from=str(LocKind.INBOUND_VEHICLE),
            ledger_to=str(LocKind.RESERVE_STAGING),
        )
        self.putaway_ticks.append(ctx.now)
        home = self._drive(DROP, HOME, ctx.now, "to_home", pallet.pallet_id)
        ctx.sched.schedule(home, Phase.COMPLETION, self._available, key=(self.driver_id,))

    def _available(self) -> None:
        self.forklift_busy = False
        self.ctx.request_dispatch()

    def _drive(self, source: str, target: str, start: int, operation: str, entity: str) -> int:
        points, arrive = self.ctx.inbound.waypoints(
            source, target, start, Fraction(self.ctx.drive_ticks_per_metre())
        )
        self.ctx.recorder.act(
            self.driver_id, ActorState.TRAVEL, operation, start, arrive, entity, waypoints=points
        )
        return arrive

    def _service(
        self, start: int, seconds: float, operation: str, pallet: InboundPallet, node: str
    ) -> int:
        end = start + self.ctx.ticks(exact(seconds))
        self.ctx.recorder.act(
            self.driver_id,
            ActorState.BUSY_SERVICE,
            operation,
            start,
            end,
            pallet.pallet_id,
            pos=self.ctx.inbound.positions[node],
        )
        return end

    def blocked(self) -> bool:
        """True when receipts remain outside or inside the area with no way to progress."""
        return bool(self.external or self.area)
