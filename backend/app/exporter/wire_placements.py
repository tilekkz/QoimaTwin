"""Deterministic finite pallet places released at the physical pickup completion."""

from collections.abc import Iterator
from typing import Any

from app.exporter.wire_locations import locations
from app.simulation.engine import Engine


def placements(
    engine: Engine, end_tick: int
) -> Iterator[tuple[tuple[int, int, int, int], dict[str, Any]]]:
    occupied: dict[str, dict[str, int]] = {}
    capacities = {place["container_id"]: place["capacity"] for place in locations(engine)}
    for tick, phase, offset, cargo, target in sorted(_operations(engine, end_tick)):
        for container, slots in occupied.items():
            previous = slots.pop(cargo, None)
            if previous is not None:
                yield _event(
                    engine, (tick, phase, offset, 2), cargo, "cargo_removed", container, previous
                )
        if target is None:
            continue
        slots = occupied.setdefault(target, {})
        slot = next((i for i in range(capacities[target]) if i not in slots.values()), None)
        if slot is None:
            raise ValueError(f"proposed location capacity exceeded: {target}")
        slots[cargo] = slot
        yield _event(engine, (tick, phase, offset, 3), cargo, "cargo_placed", target, slot)


def _event(
    engine: Engine, key: tuple[int, int, int, int], cargo: str, kind: str, container: str, slot: int
) -> tuple[tuple[int, int, int, int], dict[str, Any]]:
    return key, {
        "at_tick": key[0],
        "at_s": key[0] / engine.ctx.grid.ticks_per_second,
        "phase": key[1],
        "kind": kind,
        "entity_id": cargo,
        "payload": {"cargo_id": cargo, "container_id": container, "slot_index": slot},
    }


def _operations(engine: Engine, end_tick: int) -> list[tuple[int, int, int, str, str | None]]:
    result: list[tuple[int, int, int, str, str | None]] = []
    pallets = {
        e.entity_id: e.payload["pallet_id"]
        for e in engine.ctx.recorder.events
        if e.kind == "parcel_scanned"
    }
    opened = set()
    for action in sorted(engine.ctx.recorder.actions, key=lambda a: (a.start_tick, a.action_id)):
        if action.operation == "scan" and action.start_tick <= end_tick:
            result.append((action.start_tick, 3, 10**12, f"PCL_{action.entity_id}", None))
            live = engine.shipping.open_pallet
            pallet = pallets.get(action.entity_id or "", live.pallet_id if live else None)
            if pallet is not None and pallet not in opened:
                opened.add(pallet)
                result.append((action.start_tick, 3, 10**12, pallet, "OPEN_PALLET"))
        if action.end_tick <= end_tick and action.operation in {"pickup", "putaway"}:
            target = "RESERVE_STAGING" if action.operation == "putaway" else None
            result.append((action.end_tick, 0, -1, action.entity_id or "", target))
    for event in engine.ctx.recorder.events:
        target = {"pallet_sealed": "SEALED_PALLETS", "receipt_accepted": "RECEIVING_AREA"}.get(
            event.kind
        )
        if target:
            result.append(
                (event.at_tick, int(event.phase), event.seq, event.payload["pallet_id"], target)
            )
    return result + _buffer_operations(engine)


def _buffer_operations(engine: Engine) -> list[tuple[int, int, int, str, str | None]]:
    result: list[tuple[int, int, int, str, str | None]] = []
    containers = {*engine.packing.stations, "SHIPPING"}
    for transfer in engine.conveyor.transfers:
        if transfer.target in containers:
            result.append(
                (transfer.at_tick, 2, transfer.event_offset, transfer.cargo_id, transfer.target)
            )
    for event in engine.ctx.recorder.events:
        p, kind = event.payload, event.kind
        if kind == "pack_started":
            result.append((event.at_tick, int(event.phase), event.seq, p["tote_id"], None))
        elif kind == "order_packed":
            result.append(
                (
                    event.at_tick,
                    int(event.phase),
                    event.seq,
                    p["parcel_id"],
                    f"output:{p['pack_id']}",
                )
            )
        elif kind == "parcel_outfed":
            result.append((event.at_tick, int(event.phase), event.seq, p["parcel_id"], None))
    return result
