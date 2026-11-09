"""Action geometry in the v2 wire format."""

from typing import Any

from app.simulation.engine import Engine
from app.simulation.recorder import Action, Waypoint


def project_actions(engine: Engine, end_tick: int) -> list[dict[str, Any]]:
    tps = engine.ctx.grid.ticks_per_second
    result = []
    for action in engine.ctx.recorder.actions:
        if action.start_tick >= end_tick:
            continue
        end = min(action.end_tick, end_tick)
        row: dict[str, Any] = {
            "action_id": action.action_id,
            "actor_id": action.actor_id,
            "state": str(action.state),
            "operation": action.operation,
            "start_s": action.start_tick / tps,
            "end_s": end / tps,
            "entity_id": action.entity_id,
        }
        if action.waypoints:
            row["waypoints"] = _waypoints(action, end, tps)
        else:
            row["pos"] = list(action.pos or ())
        result.append(row)
    result.extend(_open_blocks(engine, end_tick))
    return sorted(result, key=lambda action: (action["start_s"], action["action_id"]))


def _open_blocks(engine: Engine, end_tick: int) -> list[dict[str, Any]]:
    blocks = [
        (s.packer_id, s.blocked_since, s.blocked_parcel, s.worker_pos, "output")
        for s in engine.packing.stations.values()
        if s.blocked_parcel is not None
    ]
    blocks.extend(
        (
            job.picker.actor_id,
            engine.ctx.recorder.last_end(job.picker.actor_id),
            job.order.order_id,
            engine.ctx.walk.positions[job.picker.home],
            "induction",
        )
        for job in engine.picking.jobs.values()
    )
    tps = engine.ctx.grid.ticks_per_second
    return [
        {
            "action_id": f"OPEN_{actor}",
            "actor_id": actor,
            "state": "BLOCKED",
            "operation": operation,
            "start_s": start / tps,
            "end_s": end_tick / tps,
            "entity_id": entity,
            "pos": list(pos),
        }
        for actor, start, entity, pos, operation in blocks
        if start < end_tick
    ]


def _point(point: Waypoint, tps: int) -> dict[str, Any]:
    return {"node_id": point.node_id, "pos": list(point.pos), "at_s": point.at_tick / tps}


def _waypoints(action: Action, end: int, tps: int) -> list[dict[str, Any]]:
    points = action.waypoints
    result = [_point(point, tps) for point in points if point.at_tick <= end]
    if result[-1]["at_s"] == end / tps:
        return result
    left = points[len(result) - 1]
    right = points[len(result)]
    fraction = (end - left.at_tick) / (right.at_tick - left.at_tick)
    result.append(
        {
            "node_id": f"@cutoff:{left.node_id}:{right.node_id}",
            "pos": [a + (b - a) * fraction for a, b in zip(left.pos, right.pos, strict=True)],
            "at_s": end / tps,
        }
    )
    return result
