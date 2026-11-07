"""Project the shared exact-tick resource-wait policy into wire action descriptors."""

from collections import defaultdict
from typing import Any

from app.simulation.engine import Engine
from app.simulation.recorder import Action
from app.simulation.resource_waits import derive_resource_waits


def resource_wait_actions(
    engine: Engine, end_tick: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    roster = {actor.actor_id: actor for actor in engine.ctx.inputs.actors.actors}
    by_actor: dict[str, list[Action]] = defaultdict(list)
    for action in engine.ctx.recorder.actions:
        by_actor[action.actor_id].append(action)
    actions: list[dict[str, Any]] = []
    boundary: list[dict[str, Any]] = []
    tps = engine.ctx.grid.ticks_per_second
    for index, wait in enumerate(derive_resource_waits(engine, end_tick)):
        previous = next(
            (a for a in reversed(by_actor[wait.actor_id]) if a.end_tick <= wait.start_tick), None
        )
        pos = roster[wait.actor_id].initial_pos
        if previous is not None:
            pos = previous.waypoints[-1].pos if previous.waypoints else previous.pos or pos
        zero = wait.start_tick == wait.end_tick
        row = {
            "action_id": f"WAIT_{wait.actor_id}_{index}",
            "actor_id": wait.actor_id,
            "state": "WAIT_RESOURCE",
            "operation": "wait_resource",
            "start_s": wait.start_tick / tps,
            "end_s": None if zero else wait.end_tick / tps,
            "entity_id": None,
            "pos": list(pos),
            "carrying_cargo_id": None,
            "reason": wait.reason,
            "open_ended": wait.open_ended,
            "scheduled_end_s": None,
            "destination_node_id": None,
        }
        (boundary if zero else actions).append(row)
    return actions, boundary
