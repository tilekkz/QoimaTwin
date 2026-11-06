"""Expand transfers at their journal anchors, then assign the public sequence."""

from typing import Any

from app.simulation.engine import Engine


def project_events(engine: Engine) -> list[dict[str, Any]]:
    tps = engine.ctx.grid.ticks_per_second
    rows: list[tuple[tuple[int, int, int, int, int], dict[str, Any]]] = []
    for event in engine.ctx.recorder.events:
        row = {
            "at_s": event.at_tick / tps,
            "phase": int(event.phase),
            "kind": event.kind,
            "entity_id": event.entity_id,
            "payload": {**event.payload, "at_tick": event.at_tick},
        }
        rows.append(((event.at_tick, int(event.phase), event.seq, 1, 0), row))
    for index, transfer in enumerate(engine.conveyor.transfers):
        for side, kind, cell in (
            (0, "cell_exited", transfer.source),
            (1, "cell_entered", transfer.target),
        ):
            payload = {
                "at_tick": transfer.at_tick,
                "cargo_id": transfer.cargo_id,
                "cell_id": cell,
                "transition_id": f"TR{index:09d}",
                "from_container_id": transfer.source,
                "to_container_id": transfer.target,
            }
            row = {
                "at_s": transfer.at_tick / tps,
                "phase": 2,
                "kind": kind,
                "entity_id": transfer.cargo_id,
                "payload": payload,
            }
            rows.append(((transfer.at_tick, 2, transfer.event_offset, 0, 2 * index + side), row))
    result = []
    for seq, (_, row) in enumerate(sorted(rows, key=lambda item: item[0])):
        result.append({"seq": seq, **row})
    return result
