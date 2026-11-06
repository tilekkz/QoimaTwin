"""Pack stations: finite input buffers, one packer each, blocked output (spec 01 §5, ADR 0009).

The target post is chosen at handoff by minimum reserved WIP (in transit + waiting + in service +
blocked output), tie by pack ID. The reservation is released only when the parcel enters the
outfeed. At pack completion the contents move to a new parcel and the tote returns to the pool.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.contracts.base import exact
from app.inventory.ledger import Location, LocKind
from app.simulation.conveyor_driver import CargoInfo
from app.simulation.recorder import ActorState, Vec3
from app.simulation.scheduler import Phase

if TYPE_CHECKING:
    from app.simulation.context import SimContext
    from app.simulation.engine import Engine


@dataclass(slots=True)
class Station:
    pack_id: str
    packer_id: str
    worker_pos: Vec3
    outlet: str
    capacity: int
    waiting: deque[CargoInfo] = field(default_factory=deque)
    in_service: CargoInfo | None = None
    blocked_parcel: str | None = None
    blocked_since: int = 0
    reserved_wip: int = 0


class Packing:
    def __init__(self, ctx: SimContext, engine: Engine) -> None:
        self.ctx = ctx
        self.engine = engine
        packers = {a.pack_id: a.actor_id for a in ctx.inputs.actors.by_role("packer")}
        self.stations = {
            s.pack_id: Station(
                pack_id=s.pack_id,
                packer_id=packers[s.pack_id],
                worker_pos=s.worker_pos,
                outlet=ctx.topology.pack_outlets[s.pack_id],
                capacity=ctx.config.pack_buffer_capacity,
            )
            for s in sorted(ctx.inputs.layout.pack_stations, key=lambda s: s.pack_id)
        }

    # ----- targeting -----
    def reserve_target(self) -> str:
        station = min(self.stations.values(), key=lambda s: (s.reserved_wip, s.pack_id))
        station.reserved_wip += 1
        return station.pack_id

    # ----- buffer -----
    def can_accept(self, pack_id: str) -> bool:
        station = self.stations[pack_id]
        return len(station.waiting) < station.capacity

    def accept(self, pack_id: str, tote: CargoInfo) -> None:
        self.stations[pack_id].waiting.append(tote)
        self.ctx.request_dispatch()

    # ----- dispatch (phase 3) -----
    def start_services(self) -> bool:
        changed = False
        for station in self.stations.values():
            if station.in_service or station.blocked_parcel or not station.waiting:
                continue
            self._start(station, station.waiting.popleft())
            changed = True
        return changed

    def _start(self, station: Station, tote: CargoInfo) -> None:
        ctx = self.ctx
        station.in_service = tote
        wip = Location(LocKind.PACK_WIP, station.pack_id)
        moved = ctx.ledger.transfer_location(Location(LocKind.TOTE, tote.cargo_id), wip)
        lines = len({h.sku_id for h, _ in moved})
        units = sum(q for _, q in moved)
        service = ctx.ticks(
            exact(ctx.config.pack_base_s)
            + exact(ctx.config.pack_per_line_s) * lines
            + exact(ctx.config.pack_per_unit_s) * units
        )
        ctx.recorder.emit(
            ctx.now,
            Phase.DISPATCH,
            "pack_started",
            tote.order_id,
            order_id=tote.order_id,
            pack_id=station.pack_id,
            actor_id=station.packer_id,
            tote_id=tote.cargo_id,
        )
        ctx.recorder.act(
            station.packer_id,
            ActorState.BUSY_SERVICE,
            "pack",
            ctx.now,
            ctx.now + service,
            tote.order_id,
            pos=station.worker_pos,
        )
        ctx.sched.schedule(
            ctx.now + service,
            Phase.COMPLETION,
            lambda: self._packed(station),
            key=(station.packer_id,),
        )

    def _packed(self, station: Station) -> None:
        ctx = self.ctx
        tote = station.in_service
        assert tote is not None
        parcel_id = f"PCL_{tote.order_id}"
        ctx.ledger.transfer_location(
            Location(LocKind.PACK_WIP, station.pack_id), Location(LocKind.PARCEL, parcel_id)
        )
        station.in_service = None
        station.blocked_parcel = parcel_id
        station.blocked_since = ctx.now
        ctx.recorder.emit(
            ctx.now,
            Phase.COMPLETION,
            "order_packed",
            tote.order_id,
            order_id=tote.order_id,
            pack_id=station.pack_id,
            actor_id=station.packer_id,
            tote_id=tote.cargo_id,
            parcel_id=parcel_id,
        )
        self.engine.metrics.order_packed(tote.order_id, ctx.now)
        self.engine.picking.release_tote(tote.cargo_id)
        self.engine.conveyor.register_cargo(parcel_id, "parcel", tote.order_id, "SHIPPING")
        self.engine.conveyor.request_admission(
            inlet=station.outlet,
            cargo_id=parcel_id,
            sort_key=(ctx.now, station.pack_id),
            on_admitted=lambda cell: self._outfed(station, tote.order_id, cell),
        )

    def _outfed(self, station: Station, order_id: str, cell: str) -> None:
        ctx = self.ctx
        if ctx.now > station.blocked_since:
            ctx.recorder.act(
                station.packer_id,
                ActorState.BLOCKED,
                "output",
                station.blocked_since,
                ctx.now,
                order_id,
                pos=station.worker_pos,
            )
        ctx.recorder.emit(
            ctx.now,
            Phase.CONVEYOR,
            "parcel_outfed",
            order_id,
            order_id=order_id,
            pack_id=station.pack_id,
            actor_id=station.packer_id,
            parcel_id=station.blocked_parcel,
            cell_id=cell,
        )
        station.blocked_parcel = None
        station.reserved_wip -= 1
        ctx.request_dispatch()
