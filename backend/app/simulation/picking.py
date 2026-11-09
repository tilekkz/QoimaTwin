"""Order queue, picker assignment, pick routes and handoff to the feed (spec 01 §6, ADR 0009).

FIFO by `(arrival, order_id)`. The head is checked against free active stock: a shortage rejects it.
An admissible head that waits for a picker or a tote is never bypassed. A picker walks a
nearest-neighbour route over distinct SKU stops, picks each SKU once, returns home, hands off and
holds the tote (BLOCKED) until the feed admits it.
"""

from __future__ import annotations

import heapq
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from fractions import Fraction
from typing import TYPE_CHECKING

from app.contracts.base import exact
from app.contracts.scenario import Order
from app.inventory.ledger import Holding, Location, LocKind, ReservationLine
from app.simulation.recorder import ActorState
from app.simulation.scheduler import Phase

if TYPE_CHECKING:
    from app.simulation.context import SimContext
    from app.simulation.engine import Engine


@dataclass(slots=True)
class Picker:
    actor_id: str
    home: str
    induction_id: str
    busy: bool = False


@dataclass(slots=True)
class PickJob:
    order: Order
    picker: Picker
    tote_id: str
    stops: list[tuple[str, Holding, int]] = field(default_factory=list)


class Picking:
    def __init__(self, ctx: SimContext, engine: Engine) -> None:
        self.ctx = ctx
        self.engine = engine
        homes = {i.home_node_id: i.induction_id for i in ctx.inputs.layout.inductions}
        self.pickers = [
            Picker(a.actor_id, a.home_node_id or "", homes[a.home_node_id or ""])
            for a in ctx.inputs.actors.by_role("picker")
        ]
        self.free_totes = [f"T{i:03d}" for i in range(1, ctx.config.totes_total + 1)]
        heapq.heapify(self.free_totes)
        self.allocated_totes: set[str] = set()
        self.queue: deque[Order] = deque()
        self.jobs: dict[str, PickJob] = {}

    # ----- arrivals -----
    def on_arrival(self, order: Order) -> None:
        self.queue.append(order)
        self.ctx.recorder.emit(
            self.ctx.now, Phase.ARRIVAL, "order_arrived", order.order_id, order_id=order.order_id
        )
        self.engine.metrics.order_arrived(order.order_id, self.ctx.now)
        self.ctx.request_dispatch()

    # ----- dispatch (phase 3) -----
    def assign(self) -> bool:
        """Assign or reject queue heads; returns True if anything changed."""
        changed = False
        while self.queue:
            order = self.queue[0]
            lines = self._lines(order)
            if lines is None or not self._available(lines):
                self._reject(order)
                changed = True
                continue
            picker = next((p for p in self.pickers if not p.busy), None)
            if picker is None or not self.free_totes:
                return changed
            if not self.ctx.ledger.try_reserve(order.order_id, lines):
                self._reject(order)
                changed = True
                continue
            self.queue.popleft()
            self._start(order, picker, heapq.heappop(self.free_totes), lines)
            changed = True
        return changed

    def _lines(self, order: Order) -> list[ReservationLine] | None:
        lines = []
        for line in sorted(order.lines, key=lambda line: line.sku_id):
            holding = self.ctx.sku_holding.get(line.sku_id)
            if holding is None:
                return None
            lines.append(ReservationLine(holding, line.quantity))
        return lines

    def _available(self, lines: list[ReservationLine]) -> bool:
        return all(self.ctx.ledger.available(r.holding) >= r.quantity for r in lines)

    def _reject(self, order: Order) -> None:
        self.queue.popleft()
        self.ctx.recorder.emit(
            self.ctx.now,
            Phase.DISPATCH,
            "order_rejected_inventory",
            order.order_id,
            order_id=order.order_id,
            reason="unfulfilled_inventory",
        )
        self.engine.metrics.order_rejected(order.order_id, self.ctx.now)

    def _start(
        self, order: Order, picker: Picker, tote_id: str, lines: list[ReservationLine]
    ) -> None:
        ctx = self.ctx
        picker.busy = True
        self.allocated_totes.add(tote_id)
        job = PickJob(order, picker, tote_id)
        self.jobs[order.order_id] = job
        ctx.recorder.emit(
            ctx.now,
            Phase.DISPATCH,
            "order_assigned",
            order.order_id,
            order_id=order.order_id,
            actor_id=picker.actor_id,
            tote_id=tote_id,
        )
        for line in lines:
            h = line.holding
            ctx.recorder.emit(
                ctx.now,
                Phase.DISPATCH,
                "stock_reserved",
                order.order_id,
                order_id=order.order_id,
                sku_id=h.sku_id,
                slot_id=h.location.ref,
                lot_id=h.lot_id,
                quantity=line.quantity,
            )
        self._plan_route(job, lines)

    # ----- route -----
    def _plan_route(self, job: PickJob, lines: list[ReservationLine]) -> None:
        ctx = self.ctx
        stops = {r.holding.sku_id: (ctx.slot_node[r.holding.location.ref], r) for r in lines}
        position, tick = job.picker.home, ctx.now
        while stops:
            sku = min(
                stops, key=lambda s: (ctx.walk.paths.require_distance(position, stops[s][0]), s)
            )
            node, line = stops.pop(sku)
            tick = self._walk(job, position, node, tick, f"to_{sku}")
            service = ctx.ticks(
                exact(ctx.config.pick_base_s) + exact(ctx.config.pick_per_unit_s) * line.quantity
            )
            ctx.recorder.act(
                job.picker.actor_id,
                ActorState.BUSY_SERVICE,
                "pick",
                tick,
                tick + service,
                job.order.order_id,
                pos=ctx.walk.positions[node],
            )
            tick += service
            ctx.sched.schedule(
                tick, Phase.COMPLETION, self._picked(job, line), key=(job.picker.actor_id,)
            )
            position = node
        tick = self._walk(job, position, job.picker.home, tick, "to_home")
        handoff = ctx.ticks(exact(ctx.config.handoff_s))
        ctx.recorder.act(
            job.picker.actor_id,
            ActorState.BUSY_SERVICE,
            "handoff",
            tick,
            tick + handoff,
            job.order.order_id,
            pos=ctx.walk.positions[job.picker.home],
        )
        ctx.sched.schedule(
            tick + handoff,
            Phase.COMPLETION,
            lambda: self._handoff_ready(job),
            key=(job.picker.actor_id,),
        )

    def _walk(self, job: PickJob, source: str, target: str, start: int, operation: str) -> int:
        if source == target:
            return start
        points, arrive = self.ctx.walk.waypoints(
            source, target, start, Fraction(self.ctx.walk_ticks_per_metre())
        )
        self.ctx.recorder.act(
            job.picker.actor_id,
            ActorState.TRAVEL,
            operation,
            start,
            arrive,
            job.order.order_id,
            waypoints=points,
        )
        self.engine.metrics.add_distance(
            job.picker.actor_id, self.ctx.walk.paths.require_distance(source, target)
        )
        return arrive

    def _picked(self, job: PickJob, line: ReservationLine) -> Callable[[], None]:
        def done() -> None:
            ctx = self.ctx
            tote = Location(LocKind.TOTE, job.tote_id)
            ctx.ledger.pick(job.order.order_id, line.holding, line.quantity, tote)
            ctx.recorder.emit(
                ctx.now,
                Phase.COMPLETION,
                "sku_picked",
                job.order.order_id,
                order_id=job.order.order_id,
                sku_id=line.holding.sku_id,
                slot_id=line.holding.location.ref,
                lot_id=line.holding.lot_id,
                quantity=line.quantity,
                actor_id=job.picker.actor_id,
                tote_id=job.tote_id,
            )

        return done

    # ----- handoff and induction -----
    def _handoff_ready(self, job: PickJob) -> None:
        ctx = self.ctx
        target = self.engine.packing.reserve_target()
        ctx.recorder.emit(
            ctx.now,
            Phase.COMPLETION,
            "handoff_ready",
            job.order.order_id,
            order_id=job.order.order_id,
            tote_id=job.tote_id,
            actor_id=job.picker.actor_id,
            induction_id=job.picker.induction_id,
            target_pack_id=target,
        )
        self.engine.conveyor.register_cargo(job.tote_id, "tote", job.order.order_id, target)
        self.engine.conveyor.request_admission(
            inlet=ctx.topology.induction_inlets[job.picker.induction_id],
            cargo_id=job.tote_id,
            sort_key=(ctx.now, job.picker.actor_id),
            on_admitted=lambda cell: self._inducted(job, target, cell),
        )

    def _inducted(self, job: PickJob, target: str, cell: str) -> None:
        ctx = self.ctx
        ready = ctx.recorder.last_end(job.picker.actor_id)
        if ctx.now > ready:
            ctx.recorder.act(
                job.picker.actor_id,
                ActorState.BLOCKED,
                "induction",
                ready,
                ctx.now,
                job.order.order_id,
                pos=ctx.walk.positions[job.picker.home],
            )
        ctx.recorder.emit(
            ctx.now,
            Phase.CONVEYOR,
            "tote_inducted",
            job.order.order_id,
            order_id=job.order.order_id,
            tote_id=job.tote_id,
            actor_id=job.picker.actor_id,
            induction_id=job.picker.induction_id,
            target_pack_id=target,
            cell_id=cell,
        )
        job.picker.busy = False
        del self.jobs[job.order.order_id]
        ctx.request_dispatch()

    def release_tote(self, tote_id: str) -> None:
        self.allocated_totes.remove(tote_id)
        heapq.heappush(self.free_totes, tote_id)
        self.ctx.request_dispatch()
