"""Shipping buffer, scanning and palletization (spec 01 §6 step 8, ADR 0006, ADR 0009).

One open pallet at a time. A shipper reserves the parcel and one pallet slot when the scan starts;
the parcel leaves the buffer at that moment. The 300 s age timer starts at the first placement.
Timeout or a full pallet sets SEAL_PENDING; the seal waits for outstanding scans and for space in
the sealed-pallet queue. Each timer carries a generation so a stale expiry does nothing.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from app.contracts.base import exact
from app.simulation.conveyor_driver import CargoInfo
from app.simulation.recorder import ActorState, Vec3
from app.simulation.scheduler import Phase

if TYPE_CHECKING:
    from app.simulation.context import SimContext
    from app.simulation.engine import Engine


class PalletState(StrEnum):
    OPEN = "OPEN"
    SEAL_PENDING = "SEAL_PENDING"
    SEALED = "SEALED"
    CLAIMED = "CLAIMED"
    DISPATCHED = "DISPATCHED"


@dataclass(slots=True)
class Pallet:
    pallet_id: str
    state: PalletState = PalletState.OPEN
    parcels: list[CargoInfo] = field(default_factory=list)
    reserved: int = 0
    first_placement: int | None = None
    generation: int = 0


@dataclass(slots=True)
class Shipper:
    actor_id: str
    pos: Vec3
    busy: bool = False


class Shipping:
    def __init__(self, ctx: SimContext, engine: Engine) -> None:
        self.ctx = ctx
        self.engine = engine
        self.buffer: deque[CargoInfo] = deque()
        self.shippers = [
            Shipper(a.actor_id, a.initial_pos) for a in ctx.inputs.actors.by_role("shipper")
        ]
        self.open_pallet: Pallet | None = None
        self.sealed_queue: list[Pallet] = []
        self.capacity = ctx.config.parcels_per_pallet

    # ----- buffer -----
    def can_accept(self) -> bool:
        return len(self.buffer) < self.ctx.config.shipping_buffer_capacity

    def accept(self, parcel: CargoInfo) -> None:
        self.buffer.append(parcel)
        self.ctx.recorder.emit(
            self.ctx.now,
            Phase.CONVEYOR,
            "shipping_arrived",
            parcel.order_id,
            order_id=parcel.order_id,
            parcel_id=parcel.cargo_id,
        )
        self.ctx.request_dispatch()

    # ----- dispatch (phase 3) -----
    def seal_ready(self) -> bool:
        pallet = self.open_pallet
        if pallet is None or pallet.state is not PalletState.SEAL_PENDING or pallet.reserved:
            return False
        if len(self.sealed_queue) >= self.ctx.config.sealed_pallet_queue_capacity:
            return False
        pallet.state = PalletState.SEALED
        pallet.generation += 1
        self.open_pallet = None
        self.sealed_queue.append(pallet)
        orders = [p.order_id for p in pallet.parcels]
        self.ctx.recorder.emit(
            self.ctx.now,
            Phase.DISPATCH,
            "pallet_sealed",
            pallet.pallet_id,
            pallet_id=pallet.pallet_id,
            parcel_ids=[p.cargo_id for p in pallet.parcels],
            order_ids=orders,
        )
        self.engine.outbound.add_task(pallet)
        return True

    def start_scans(self) -> bool:
        changed = False
        for shipper in self.shippers:
            if shipper.busy or not self.buffer:
                continue
            pallet = self._pallet_with_space()
            if pallet is None:
                break
            self._scan(shipper, pallet, self.buffer.popleft())
            changed = True
        return changed

    def _pallet_with_space(self) -> Pallet | None:
        if self.open_pallet is None:
            self.open_pallet = Pallet(self.ctx.next_id("PAL", 4))
        pallet = self.open_pallet
        if pallet.state is not PalletState.OPEN:
            return None
        if len(pallet.parcels) + pallet.reserved >= self.capacity:
            return None
        return pallet

    def _scan(self, shipper: Shipper, pallet: Pallet, parcel: CargoInfo) -> None:
        ctx = self.ctx
        shipper.busy = True
        pallet.reserved += 1
        end = ctx.now + ctx.ticks(exact(ctx.config.shipping_scan_s))
        ctx.recorder.act(
            shipper.actor_id,
            ActorState.BUSY_SERVICE,
            "scan",
            ctx.now,
            end,
            parcel.order_id,
            pos=shipper.pos,
        )
        ctx.sched.schedule(
            end,
            Phase.COMPLETION,
            lambda: self._placed(shipper, pallet, parcel),
            key=(shipper.actor_id,),
        )

    def _placed(self, shipper: Shipper, pallet: Pallet, parcel: CargoInfo) -> None:
        ctx = self.ctx
        shipper.busy = False
        pallet.reserved -= 1
        pallet.parcels.append(parcel)
        ctx.recorder.emit(
            ctx.now,
            Phase.COMPLETION,
            "parcel_scanned",
            parcel.order_id,
            order_id=parcel.order_id,
            parcel_id=parcel.cargo_id,
            pallet_id=pallet.pallet_id,
            actor_id=shipper.actor_id,
        )
        if pallet.first_placement is None:
            pallet.first_placement = ctx.now
            generation = pallet.generation
            ctx.sched.schedule(
                ctx.now + ctx.ticks(exact(ctx.config.pallet_max_age_s)),
                Phase.COMPLETION,
                lambda: self._expired(pallet, generation),
                key=("pallet", pallet.pallet_id),
            )
        if len(pallet.parcels) >= self.capacity and pallet.state is PalletState.OPEN:
            self._mark_pending(pallet, "full")
        ctx.request_dispatch()

    def _expired(self, pallet: Pallet, generation: int) -> None:
        if pallet.generation != generation or pallet.state is not PalletState.OPEN:
            return
        self._mark_pending(pallet, "age")
        self.ctx.request_dispatch()

    def _mark_pending(self, pallet: Pallet, trigger: str) -> None:
        pallet.state = PalletState.SEAL_PENDING
        self.ctx.recorder.emit(
            self.ctx.now,
            Phase.COMPLETION,
            "pallet_seal_pending",
            pallet.pallet_id,
            pallet_id=pallet.pallet_id,
            trigger=trigger,
            outstanding_reservations=pallet.reserved,
        )

    def release_queue_place(self, pallet: Pallet) -> None:
        self.sealed_queue.remove(pallet)
        self.ctx.request_dispatch()
