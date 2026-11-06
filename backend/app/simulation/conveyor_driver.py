"""Runs atomic conveyor ticks inside the DES (ADR 0003 phase 2, ADR 0004).

A tick runs at every integer second while cargo is on the belt or an admission request waits.
Order inside the tick: belt moves and exits first, then admissions into inlet cells that are free
after the moves. New cargo first moves on the next tick.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.conveyor.topology import ExitKind
from app.conveyor.transfer import EXIT, Belt, plan_tick
from app.simulation.scheduler import Phase

if TYPE_CHECKING:
    from app.simulation.context import SimContext
    from app.simulation.engine import Engine


@dataclass(frozen=True, slots=True)
class CargoInfo:
    cargo_id: str
    kind: str
    order_id: str
    target: str


@dataclass(slots=True)
class AdmissionRequest:
    inlet: str
    cargo_id: str
    sort_key: tuple[int, str]
    on_admitted: Callable[[str], None]


@dataclass(frozen=True, slots=True)
class CellTransfer:
    """Compact atomic transfer record; the exporter expands it to cell_exited/cell_entered."""

    at_tick: int
    cargo_id: str
    source: str
    target: str


class ConveyorDriver:
    def __init__(self, ctx: SimContext, engine: Engine) -> None:
        self.ctx = ctx
        self.engine = engine
        topo = ctx.topology
        self.belt = Belt(successors=topo.successors, predecessors=topo.predecessors)
        self.occupancy: dict[str, str] = {}
        self.cursors: dict[str, int] = {}
        self.cargo: dict[str, CargoInfo] = {}
        self.requests: list[AdmissionRequest] = []
        self.transfers: list[CellTransfer] = []

    def register_cargo(self, cargo_id: str, kind: str, order_id: str, target: str) -> None:
        self.cargo[cargo_id] = CargoInfo(cargo_id, kind, order_id, target)

    def request_admission(
        self,
        inlet: str,
        cargo_id: str,
        sort_key: tuple[int, str],
        on_admitted: Callable[[str], None],
    ) -> None:
        self.requests.append(AdmissionRequest(inlet, cargo_id, sort_key, on_admitted))
        self._wake()

    def has_work(self) -> bool:
        return bool(self.occupancy or self.requests)

    # ----- tick -----
    def _wake(self) -> None:
        ctx = self.ctx
        tick = ctx.grid.ceil_to_second(ctx.now)
        running = ctx.sched.running_phase
        if tick == ctx.now and running is not None and running >= Phase.CONVEYOR:
            tick += ctx.grid.ticks_per_second
        ctx.sched.schedule(tick, Phase.CONVEYOR, self._tick, unique="conveyor")

    def _route(self, cargo_id: str, cell: str) -> str:
        info = self.cargo[cargo_id]
        exit_ = self.ctx.topology.exits.get(cell)
        if exit_ is not None and exit_.target_id == info.target:
            return EXIT
        nxt = self.ctx.topology.next_cell_towards(cell, info.target)
        return EXIT if nxt is None else nxt

    def _exit_open(self, cargo_id: str, cell: str) -> bool:
        exit_ = self.ctx.topology.exits[cell]
        if exit_.kind is ExitKind.PACK_BUFFER:
            return self.engine.packing.can_accept(exit_.target_id)
        return self.engine.shipping.can_accept()

    def _tick(self) -> None:
        now = self.ctx.now
        result = plan_tick(self.belt, self.occupancy, self._route, self._exit_open, self.cursors)
        self.occupancy, self.cursors = result.occupancy, result.cursors
        for move in result.moves:
            self.transfers.append(CellTransfer(now, move.cargo, move.source, move.target))
        for out in result.exits:
            exit_ = self.ctx.topology.exits[out.source]
            self.transfers.append(CellTransfer(now, out.cargo, out.source, exit_.target_id))
            info = self.cargo.pop(out.cargo)
            if exit_.kind is ExitKind.PACK_BUFFER:
                self.engine.packing.accept(exit_.target_id, info)
            else:
                self.engine.shipping.accept(info)
        self._admit(now)
        if self.has_work():
            self.ctx.sched.schedule(
                now + self.ctx.grid.ticks_per_second, Phase.CONVEYOR, self._tick, unique="conveyor"
            )

    def _admit(self, now: int) -> None:
        waiting: list[AdmissionRequest] = []
        for request in sorted(self.requests, key=lambda r: (r.inlet, r.sort_key, r.cargo_id)):
            if request.inlet in self.occupancy:
                waiting.append(request)
                continue
            self.occupancy[request.inlet] = request.cargo_id
            self.transfers.append(CellTransfer(now, request.cargo_id, "inlet", request.inlet))
            request.on_admitted(request.inlet)
        self.requests = waiting
