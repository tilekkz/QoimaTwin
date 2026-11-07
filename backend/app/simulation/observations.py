"""Settled resource samples and one horizon inventory snapshot (ADR 0013)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from app.conveyor.transfer import plan_tick
from app.inventory.ledger import LocKind
from app.simulation.receiving import InboundState

if TYPE_CHECKING:
    from app.simulation.engine import Engine

type Inventory = dict[str, dict[str, int]]


@dataclass(frozen=True, slots=True)
class ResourceSample:
    at_tick: int
    occupied_cells: int
    jammed_cells: int
    free_totes: int
    receiving_area: int = 0
    station_wip: tuple[tuple[str, int], ...] = ()


def queues(engine: Engine) -> dict[str, int]:
    result = {
        "orders": len(engine.picking.queue),
        "shipping": len(engine.shipping.buffer),
        "outbound": len(engine.outbound.tasks),
        "receiving_external": len(engine.receiving.external),
        "receiving": sum(p.state is InboundState.WAITING for p in engine.receiving.area),
        "putaway": sum(p.state is InboundState.PROCESSED for p in engine.receiving.area),
    }
    result.update({f"pack:{s.pack_id}": len(s.waiting) for s in engine.packing.stations.values()})
    return result


def inventory_balances(engine: Engine) -> Inventory:
    result: Inventory = {sku: dict.fromkeys(LocKind, 0) for sku in engine.ctx.ledger.skus()}
    for holding, quantity in engine.ctx.ledger._balances.items():
        result[holding.sku_id][holding.location.kind] += quantity
    return result


class MetricObserver:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.horizon = engine.ctx.ticks(engine.ctx.inputs.scenario.horizon_s)
        self.horizon_inventory = inventory_balances(engine)
        self.samples: list[ResourceSample] = []
        self._event_cursor = 0
        self._picked_units: Counter[str] = Counter()
        self._required_units = {
            order.order_id: sum(line.quantity for line in order.lines)
            for order in engine.ctx.inputs.scenario.orders
        }
        self._jam_key: object = None
        self._jam_count = 0
        self._sample(0)

    def observe(self, tick: int, next_tick: int | None) -> None:
        self._milestones()
        self._sample(tick)
        if tick < self.horizon and (next_tick is None or next_tick >= self.horizon):
            self.horizon_inventory = inventory_balances(self.engine)

    def _milestones(self) -> None:
        events, records = self.engine.ctx.recorder.events, self.engine.metrics.orders
        for event in events[self._event_cursor :]:
            record = records.get(event.entity_id)
            if record is None:
                continue
            if event.kind == "order_assigned":
                record.admitted = event.at_tick
            elif event.kind == "sku_picked":
                self._picked_units[event.entity_id] += event.payload["quantity"]
                if self._picked_units[event.entity_id] == self._required_units.get(event.entity_id):
                    record.picked = event.at_tick
        self._event_cursor = len(events)

    def _sample(self, tick: int) -> None:
        engine = self.engine
        queue_samples = engine.metrics.queue_samples
        if queue_samples and queue_samples[-1][0] == tick:
            queue_samples.pop()
        queue_samples.append((tick, queues(engine)))
        sample = ResourceSample(
            tick,
            len(engine.conveyor.occupancy),
            self._jammed(),
            len(engine.picking.free_totes),
            len(engine.receiving.area),
            tuple((s.pack_id, s.reserved_wip) for s in engine.packing.stations.values()),
        )
        if self.samples and self.samples[-1].at_tick == tick:
            self.samples.pop()
        if not self.samples or replace(self.samples[-1], at_tick=tick) != sample:
            self.samples.append(sample)

    def _jammed(self) -> int:
        engine, conveyor = self.engine, self.engine.conveyor
        key = (
            tuple(conveyor.occupancy.items()),
            tuple(conveyor.cursors.items()),
            tuple((cargo, conveyor.cargo[cargo].target) for cargo in conveyor.occupancy.values()),
            tuple(engine.packing.can_accept(s) for s in engine.packing.stations),
            engine.shipping.can_accept(),
        )
        if key != self._jam_key:
            planned = plan_tick(
                conveyor.belt,
                conveyor.occupancy,
                conveyor._route,
                conveyor._exit_open,
                conveyor.cursors,
            )
            self._jam_count = len(conveyor.occupancy) - len(planned.moves) - len(planned.exits)
            self._jam_key = key
        return self._jam_count
