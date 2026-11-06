"""Simulation engine: wires subsystems to the phase scheduler and runs to drain (ADR 0001, 0003).

Phase 1 delivers orders; phase 2 runs conveyor ticks; phase 3 runs one coalesced dispatch cycle
repeated to a fixed point: seal pallets, assign forklift tasks, start pack services and scans,
assign FIFO orders to pickers.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from functools import partial

from app.conveyor.topology import ConveyorTopology
from app.simulation.checkpoint import Checkpointer
from app.simulation.clock import TimeGrid
from app.simulation.context import GraphGeometry, RunInputs, SimContext, build_ledger
from app.simulation.conveyor_driver import ConveyorDriver
from app.simulation.invariants import check_invariants as verify_invariants
from app.simulation.metrics import Metrics
from app.simulation.metrics_summary import queues
from app.simulation.outbound import Outbound
from app.simulation.packing import Packing
from app.simulation.picking import Picking
from app.simulation.receiving import Receiving
from app.simulation.recorder import Recorder
from app.simulation.scheduler import Phase, PhaseScheduler
from app.simulation.shipping import Shipping
from app.simulation.snapshot_state import StateCapture

MAX_DISPATCH_ROUNDS = 10_000


class RunStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


class Termination(StrEnum):
    DRAINED = "drained"
    UNFULFILLED_INVENTORY = "unfulfilled_inventory"
    MAX_DRAIN = "max_drain"
    DEADLOCK = "deadlock"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class RunOutcome:
    status: RunStatus
    termination: Termination
    horizon_tick: int
    end_tick: int


class Engine:
    def __init__(self, inputs: RunInputs, *, check_invariants: bool = False) -> None:
        layout = inputs.layout
        grid = TimeGrid.for_inputs(layout, inputs.config)
        ledger, sku_holding = build_ledger(inputs)
        self.ctx = SimContext(
            inputs=inputs,
            grid=grid,
            sched=PhaseScheduler(),
            recorder=Recorder(),
            ledger=ledger,
            topology=ConveyorTopology.from_layout(layout),
            walk=GraphGeometry.of(layout.picker_graph),
            outbound=GraphGeometry.of(layout.forklift_graphs.outbound),
            inbound=GraphGeometry.of(layout.forklift_graphs.inbound),
            sku_holding=sku_holding,
            slot_node={s.slot_id: s.service_node_id for s in layout.slots if s.service_node_id},
        )
        self.ctx.dispatch_handler = self._dispatch_cycle
        self.metrics = Metrics()
        self.picking = Picking(self.ctx, self)
        self.conveyor = ConveyorDriver(self.ctx, self)
        self.packing = Packing(self.ctx, self)
        self.shipping = Shipping(self.ctx, self)
        self.outbound = Outbound(self.ctx, self)
        self.receiving = Receiving(self.ctx, self)
        self.check_invariants = check_invariants
        self.checkpoints = Checkpointer(
            self.ctx.ticks(inputs.config.snapshot_interval_s), StateCapture(self), self._last_seq
        )
        self.ctx.sched.on_tick_settled = self._on_tick_settled
        self._schedule_arrivals()
        self._schedule_receipts()
        horizon = self.ctx.ticks(inputs.scenario.horizon_s)
        deadline = horizon + self.ctx.ticks(inputs.config.max_drain_s)
        self.checkpoints.begin(self.ctx.sched.peek_next_tick(), deadline)

    def _last_seq(self) -> int:
        return len(self.ctx.recorder.events) - 1

    def _on_tick_settled(self, tick: int, next_tick: int | None) -> None:
        if self.check_invariants:
            verify_invariants(self)
        self.metrics.queue_samples.append((tick, queues(self)))
        self.checkpoints.on_tick_settled(tick, next_tick)

    def _schedule_arrivals(self) -> None:
        for order in sorted(
            self.ctx.inputs.scenario.orders, key=lambda o: (o.arrival_s, o.order_id)
        ):
            tick = self.ctx.ticks(order.arrival_s)
            self.ctx.sched.schedule(
                tick,
                Phase.ARRIVAL,
                partial(self.picking.on_arrival, order),
                key=(order.order_id,),
            )

    def _schedule_receipts(self) -> None:
        receipts = sorted(
            self.ctx.inputs.scenario.receipts, key=lambda r: (r.arrival_s, r.receipt_id)
        )
        for receipt in receipts:
            self.ctx.sched.schedule(
                self.ctx.ticks(receipt.arrival_s),
                Phase.ARRIVAL,
                partial(self.receiving.on_arrival, receipt),
                key=(receipt.receipt_id,),
            )

    def _dispatch_cycle(self) -> None:
        for _ in range(MAX_DISPATCH_ROUNDS):
            self.ctx.dispatch_dirty = False
            changed = self.receiving.admit()
            changed |= self.shipping.seal_ready()
            changed |= self.outbound.assign()
            changed |= self.packing.start_services()
            changed |= self.shipping.start_scans()
            changed |= self.receiving.start_services()
            changed |= self.receiving.assign_putaway()
            changed |= self.picking.assign()
            if not changed and not self.ctx.dispatch_dirty:
                return
        raise RuntimeError("dispatch cycle did not reach a fixed point")

    def run(self) -> RunOutcome:
        if self.check_invariants:
            verify_invariants(self)
        ctx = self.ctx
        horizon = ctx.ticks(ctx.inputs.scenario.horizon_s)
        deadline = horizon + ctx.ticks(ctx.config.max_drain_s)
        ctx.sched.run(until=deadline + 1)
        if ctx.sched.pending_count():
            return RunOutcome(RunStatus.PARTIAL, Termination.MAX_DRAIN, horizon, deadline)
        end = ctx.now
        if self.receiving.blocked():
            return RunOutcome(RunStatus.PARTIAL, Termination.DEADLOCK, horizon, end)
        if self.metrics.counts()["unfulfilled_inventory_total"]:
            return RunOutcome(RunStatus.PARTIAL, Termination.UNFULFILLED_INVENTORY, horizon, end)
        return RunOutcome(RunStatus.COMPLETE, Termination.DRAINED, horizon, end)
