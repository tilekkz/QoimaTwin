"""One atomic transfer record per cell move, anchored to the domain journal."""

from collections.abc import Iterator
from heapq import merge
from typing import Any

from app.exporter.wire_derived import actor_changes, milestones, receipt_pickups, stock_moves
from app.exporter.wire_placements import placements
from app.simulation.engine import Engine

type Key = tuple[int, int, int, int]
type Row = dict[str, Any]


def wire_events(engine: Engine, end_tick: int, actions: list[Row]) -> list[Row]:
    rows = merge(
        _domain(engine),
        _moves(engine),
        _attachments(engine, end_tick),
        placements(engine, end_tick),
        milestones(engine),
        stock_moves(engine),
        receipt_pickups(engine, end_tick),
        actor_changes(engine, actions),
        _receipt_arrivals(engine, end_tick),
        key=lambda p: p[0],
    )
    return [{"seq": index, **row} for index, (_, row) in enumerate(rows)]


def _receipt_arrivals(engine: Engine, end_tick: int) -> Iterator[tuple[Key, Row]]:
    for index, receipt in enumerate(
        sorted(engine.ctx.inputs.scenario.receipts, key=lambda r: (r.arrival_s, r.receipt_id))
    ):
        tick = engine.ctx.ticks(receipt.arrival_s)
        if tick <= end_tick and receipt.arrival_s < engine.ctx.inputs.scenario.horizon_s:
            yield (
                (tick, 1, index, 0),
                _event(
                    engine,
                    tick,
                    1,
                    "receipt_arrived",
                    receipt.receipt_id,
                    {
                        "receipt_id": receipt.receipt_id,
                        "sku_id": receipt.sku_id,
                        "quantity": receipt.quantity,
                    },
                ),
            )


def _event(engine: Engine, tick: int, phase: int, kind: str, entity: str, payload: Row) -> Row:
    return {
        "at_tick": tick,
        "at_s": tick / engine.ctx.grid.ticks_per_second,
        "phase": phase,
        "kind": kind,
        "entity_id": entity,
        "payload": payload,
    }


def _domain(engine: Engine) -> Iterator[tuple[Key, Row]]:
    for event in engine.ctx.recorder.events:
        row = _event(
            engine,
            event.at_tick,
            int(event.phase),
            event.kind,
            event.entity_id,
            dict(event.payload),
        )
        yield (event.at_tick, int(event.phase), event.seq, 1), row


def _moves(engine: Engine) -> Iterator[tuple[Key, Row]]:
    sources = {cell: f"inlet:{name}" for name, cell in engine.ctx.topology.induction_inlets.items()}
    sources.update(
        {cell: f"output:{name}" for name, cell in engine.ctx.topology.pack_outlets.items()}
    )
    for transfer in engine.conveyor.transfers:
        row = _event(
            engine,
            transfer.at_tick,
            2,
            "cell_moved",
            transfer.cargo_id,
            {
                "cargo_id": transfer.cargo_id,
                "from": sources[transfer.target] if transfer.source == "inlet" else transfer.source,
                "to": transfer.target,
            },
        )
        yield (transfer.at_tick, 2, transfer.event_offset, 0), row


def _attachments(engine: Engine, end_tick: int) -> Iterator[tuple[Key, Row]]:
    vehicles = {v.driver_actor_id: v.vehicle_id for v in engine.ctx.inputs.actors.vehicles}
    rows: list[tuple[Key, Row]] = []
    for action in engine.ctx.recorder.actions:
        if action.actor_id not in vehicles or action.end_tick > end_tick:
            continue
        if action.operation == "pickup":
            kind = "cargo_attached"
            payload = {"cargo_id": action.entity_id, "vehicle_id": vehicles[action.actor_id]}
        elif action.operation in {"loading", "putaway"}:
            kind = "cargo_detached"
            target = "DOCK_OUT" if action.operation == "loading" else "RESERVE_STAGING"
            payload = {
                "cargo_id": action.entity_id,
                "vehicle_id": vehicles[action.actor_id],
                "container_id": target,
            }
        else:
            continue
        row = _event(engine, action.end_tick, 0, kind, action.entity_id or "", payload)
        rows.append(((action.end_tick, 0, -1, len(rows)), row))
    yield from sorted(rows, key=lambda pair: pair[0])
