"""Outbound forklift: sealed pallet to the dock (spec 01 §6 step 9, ADR 0006, ADR 0009).

The driver and the vehicle share one trajectory. A sealed pallet keeps its queue place until the
pickup completes. Dispatch happens when the drop at the dock completes; the return trip does not
start new work until the forklift is home.
"""

from __future__ import annotations

from collections import deque
from fractions import Fraction
from typing import TYPE_CHECKING

from app.contracts.base import exact
from app.inventory.ledger import Location, LocKind
from app.simulation.recorder import ActorState
from app.simulation.scheduler import Phase
from app.simulation.shipping import Pallet, PalletState

if TYPE_CHECKING:
    from app.simulation.context import SimContext
    from app.simulation.engine import Engine

HOME, PICK, DROP = "FO_HOME", "FO_PICK", "FO_DROP"
DOCK_ID = "DOCK_OUT"


class Outbound:
    def __init__(self, ctx: SimContext, engine: Engine) -> None:
        self.ctx = ctx
        self.engine = engine
        vehicle = next(v for v in ctx.inputs.actors.vehicles if v.graph_id == "outbound")
        self.driver_id = vehicle.driver_actor_id
        self.vehicle_id = vehicle.vehicle_id
        self.tasks: deque[Pallet] = deque()
        self.busy = False
        self.current_pallet: Pallet | None = None

    def add_task(self, pallet: Pallet) -> None:
        self.tasks.append(pallet)

    def assign(self) -> bool:
        if self.busy or not self.tasks:
            return False
        pallet = self.tasks.popleft()
        self.current_pallet = pallet
        pallet.state = PalletState.CLAIMED
        self.busy = True
        arrive = self._drive(HOME, PICK, self.ctx.now, "to_pickup", pallet.pallet_id)
        end = self._service(arrive, self.ctx.config.forklift_pickup_s, "pickup", pallet)
        self.ctx.sched.schedule(
            end, Phase.COMPLETION, lambda: self._picked_up(pallet), key=(self.driver_id,)
        )
        return True

    def _picked_up(self, pallet: Pallet) -> None:
        self.engine.shipping.release_queue_place(pallet)
        arrive = self._drive(PICK, DROP, self.ctx.now, "to_dock", pallet.pallet_id)
        end = self._service(arrive, self.ctx.config.forklift_drop_s, "loading", pallet)
        self.ctx.sched.schedule(
            end, Phase.COMPLETION, lambda: self._dispatched(pallet), key=(self.driver_id,)
        )

    def _dispatched(self, pallet: Pallet) -> None:
        ctx = self.ctx
        pallet.state = PalletState.DISPATCHED
        dock = Location(LocKind.DISPATCHED, DOCK_ID)
        for parcel in pallet.parcels:
            ctx.ledger.transfer_location(Location(LocKind.PARCEL, parcel.cargo_id), dock)
            ctx.recorder.emit(
                ctx.now,
                Phase.COMPLETION,
                "order_dispatched",
                parcel.order_id,
                order_id=parcel.order_id,
                parcel_id=parcel.cargo_id,
                pallet_id=pallet.pallet_id,
                actor_id=self.driver_id,
                dock_id=DOCK_ID,
            )
            self.engine.metrics.order_dispatched(parcel.order_id, ctx.now)
        home = self._drive(DROP, HOME, ctx.now, "to_home", pallet.pallet_id)
        ctx.sched.schedule(home, Phase.COMPLETION, self._available, key=(self.driver_id,))

    def _available(self) -> None:
        self.busy = False
        self.current_pallet = None
        self.ctx.request_dispatch()

    def _drive(self, source: str, target: str, start: int, operation: str, entity: str) -> int:
        points, arrive = self.ctx.outbound.waypoints(
            source, target, start, Fraction(self.ctx.drive_ticks_per_metre())
        )
        self.ctx.recorder.act(
            self.driver_id, ActorState.TRAVEL, operation, start, arrive, entity, waypoints=points
        )
        return arrive

    def _service(self, start: int, seconds: float, operation: str, pallet: Pallet) -> int:
        end = start + self.ctx.ticks(exact(seconds))
        node = PICK if operation == "pickup" else DROP
        self.ctx.recorder.act(
            self.driver_id,
            ActorState.BUSY_SERVICE,
            operation,
            start,
            end,
            pallet.pallet_id,
            pos=self.ctx.outbound.positions[node],
        )
        return end
