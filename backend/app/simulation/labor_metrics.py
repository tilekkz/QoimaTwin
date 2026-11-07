"""Executed actor effort and distance, clipped at an observation boundary."""

from __future__ import annotations

from collections import Counter, defaultdict
from itertools import pairwise
from math import dist
from typing import TYPE_CHECKING, Any

from app.simulation.recorder import Action
from app.simulation.resource_metrics import intervals
from app.simulation.resource_waits import derive_resource_waits

if TYPE_CHECKING:
    from app.simulation.engine import Engine


def open_blocks(engine: Engine) -> list[tuple[str, int]]:
    result = [
        (s.packer_id, s.blocked_since)
        for s in engine.packing.stations.values()
        if s.blocked_parcel is not None
    ]
    result.extend(
        (job.picker.actor_id, engine.ctx.recorder.last_end(job.picker.actor_id))
        for job in engine.picking.jobs.values()
    )
    return result


def actor_ticks(engine: Engine, cutoff: int) -> dict[str, Counter[str]]:
    result: dict[str, Counter[str]] = defaultdict(Counter)
    for action in engine.ctx.recorder.actions:
        duration = max(0, min(action.end_tick, cutoff) - max(0, action.start_tick))
        result[action.actor_id][action.state.value] += duration
    for actor, start in open_blocks(engine):
        result[actor]["BLOCKED"] += max(0, cutoff - start)
    for wait in derive_resource_waits(engine, cutoff):
        result[wait.actor_id]["WAIT_RESOURCE"] += wait.end_tick - wait.start_tick
    return result


def distance_at(action: Action, cutoff: int) -> float:
    return sum(
        dist(left.pos, right.pos)
        * max(0, min(right.at_tick, cutoff) - max(0, left.at_tick))
        / (right.at_tick - left.at_tick)
        for left, right in pairwise(action.waypoints)
        if right.at_tick > left.at_tick
    )


def picker_summary(engine: Engine, cutoff: int) -> dict[str, dict[str, float]]:
    states, tps = actor_ticks(engine, cutoff), engine.ctx.grid.ticks_per_second
    distances: dict[str, float] = defaultdict(float)
    for action in engine.ctx.recorder.actions:
        distances[action.actor_id] += distance_at(action, cutoff)
    return {
        actor.actor_id: {
            "distance_m": distances[actor.actor_id],
            "travel_s": states[actor.actor_id]["TRAVEL"] / tps,
            "service_s": states[actor.actor_id]["BUSY_SERVICE"] / tps,
            "blocked_s": states[actor.actor_id]["BLOCKED"] / tps,
            "wait_resource_s": states[actor.actor_id]["WAIT_RESOURCE"] / tps,
        }
        for actor in engine.ctx.inputs.actors.by_role("picker")
    }


def station_summary(
    engine: Engine, cutoff: int, queue_mean: dict[str, float | None], *, inclusive: bool
) -> dict[str, Any]:
    states, tps = actor_ticks(engine, cutoff), engine.ctx.grid.ticks_per_second
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for event in engine.ctx.recorder.events:
        seen = event.at_tick <= cutoff if inclusive else event.at_tick < cutoff
        if seen and event.kind in {"pack_started", "order_packed"}:
            counts[event.payload["pack_id"]][event.kind] += 1
    result = {}
    samples = intervals(engine.observer.samples, cutoff)
    for station in engine.packing.stations.values():
        value = states[station.packer_id]
        service, blocked = value["BUSY_SERVICE"], value["BLOCKED"]
        result[station.pack_id] = {
            "started_total": counts[station.pack_id]["pack_started"],
            "packed_total": counts[station.pack_id]["order_packed"],
            "service_s": service / tps,
            "blocked_output_s": blocked / tps,
            "queue_mean": queue_mean[f"pack:{station.pack_id}"],
            "reserved_wip_mean": sum(
                dict(sample.station_wip).get(station.pack_id, 0) * width
                for sample, width in samples
            )
            / cutoff
            if cutoff
            else None,
            "reserved_wip_max": max(
                (dict(s.station_wip).get(station.pack_id, 0) for s, _ in samples), default=0
            ),
            "utilization": {
                "active": service / cutoff if cutoff else None,
                "blocked": blocked / cutoff if cutoff else None,
            },
        }
    return result


def labor_by_role(engine: Engine, cutoff: int) -> dict[str, dict[str, float]]:
    roster = {a.actor_id: a.role for a in engine.ctx.inputs.actors.actors}
    totals = {role: Counter[str]() for role in roster.values()}
    for actor_id, states in actor_ticks(engine, cutoff).items():
        totals[roster[actor_id]].update(states)
    tps = engine.ctx.grid.ticks_per_second
    return {
        role: {
            "travel_s": states["TRAVEL"] / tps,
            "service_s": states["BUSY_SERVICE"] / tps,
            "active_s": (states["TRAVEL"] + states["BUSY_SERVICE"]) / tps,
            "blocked_s": states["BLOCKED"] / tps,
            "wait_resource_s": states["WAIT_RESOURCE"] / tps,
        }
        for role, states in totals.items()
    }


def blocking_summary(engine: Engine, cutoff: int) -> dict[str, float]:
    totals: Counter[str] = Counter()
    for action in engine.ctx.recorder.actions:
        if action.state.value == "BLOCKED":
            totals[action.operation] += max(0, min(action.end_tick, cutoff) - action.start_tick)
    roles = {actor.actor_id: actor.role for actor in engine.ctx.inputs.actors.actors}
    for actor, start in open_blocks(engine):
        operation = "induction" if roles[actor] == "picker" else "output"
        totals[operation] += max(0, cutoff - start)
    tps = engine.ctx.grid.ticks_per_second
    return {"induction_s": totals["induction"] / tps, "pack_output_s": totals["output"] / tps}
