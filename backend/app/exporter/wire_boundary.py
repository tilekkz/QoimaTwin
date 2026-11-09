"""Zero-exposure work begun at the cutoff is a state descriptor, never a fake interval."""

from typing import Any

from app.exporter.wire_actions import normalize_actions
from app.exporter.wire_block_reasons import split_conveyor_waits
from app.exporter.wire_waits import resource_wait_actions
from app.simulation.engine import Engine


def boundary_actions(engine: Engine, end_tick: int) -> list[dict[str, Any]]:
    tps = engine.ctx.grid.ticks_per_second
    result = [
        {
            "action_id": a.action_id,
            "actor_id": a.actor_id,
            "state": str(a.state),
            "operation": a.operation,
            "start_s": end_tick / tps,
            "end_s": None,
            "entity_id": a.entity_id,
            "pos": list(a.waypoints[0].pos if a.waypoints else a.pos or ()),
        }
        for a in engine.ctx.recorder.actions
        if a.start_tick == end_tick
    ]
    for job in engine.picking.jobs.values():
        if engine.ctx.recorder.last_end(job.picker.actor_id) == end_tick:
            result.append(
                _block(
                    job.picker.actor_id,
                    job.order.order_id,
                    "induction",
                    list(engine.ctx.walk.positions[job.picker.home]),
                    end_tick / tps,
                )
            )
    for station in engine.packing.stations.values():
        if station.blocked_parcel is not None and station.blocked_since == end_tick:
            result.append(
                _block(
                    station.packer_id,
                    station.blocked_parcel.removeprefix("PCL_"),
                    "output",
                    list(station.worker_pos),
                    end_tick / tps,
                )
            )
    normalize_actions(engine, result, end_tick)
    result += resource_wait_actions(engine, end_tick)[1]
    return split_conveyor_waits(result, tps, engine.ctx.ticks(engine.ctx.config.conveyor_tick_s))


def _block(
    actor: str, entity: str, operation: str, pos: list[float], seconds: float
) -> dict[str, Any]:
    return {
        "action_id": f"OPEN_{actor}",
        "actor_id": actor,
        "state": "BLOCKED",
        "operation": operation,
        "start_s": seconds,
        "end_s": None,
        "entity_id": entity,
        "pos": pos,
    }
