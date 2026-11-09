"""Public snapshot projection and action coverage without scheduler descriptors."""

from bisect import bisect_right
from collections import defaultdict
from typing import Any

from app.exporter.wire_positions import apply_position
from app.simulation.engine import Engine
from app.storage.canonical_json import sha256_hex


def snapshots(
    engine: Engine, events: list[dict[str, Any]], actions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    ticks = [event["at_tick"] for event in events]
    by_actor: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for action in actions:
        by_actor[action["actor_id"]].append(action)
    result = []
    positions: dict[str, Any] = {}
    cursor = 0
    tps = engine.ctx.grid.ticks_per_second
    for snapshot in engine.checkpoints.snapshots:
        state, seconds = snapshot.state, snapshot.at_tick / tps
        while cursor < len(events) and events[cursor]["at_tick"] <= snapshot.at_tick:
            apply_position(positions, events[cursor])
            cursor += 1
        state["placements"] = {cargo: dict(place) for cargo, place in positions.items()}
        state.pop("timers", None)
        for actor in state["actors"]:
            _actor(actor, by_actor[actor["actor_id"]], seconds, tps)
        normalize_state(state)
        result.append(
            {
                "at_s": seconds,
                "at_tick": snapshot.at_tick,
                "last_seq": bisect_right(ticks, snapshot.at_tick) - 1,
                "state_hash": sha256_hex(state),
                "state": state,
            }
        )
    return result


def normalize_state(state: dict[str, Any]) -> None:
    state["orders"]["picking"].sort(key=lambda job: job["order_id"])
    state["orders"]["status"] = {
        key: value
        for key, value in state["orders"]["status"].items()
        if value not in {"dispatched", "unfulfilled_inventory"}
    }
    for key in ("free", "allocated"):
        state["totes"][key].sort()
    state["conveyor"]["cargo"].sort(key=lambda cargo: cargo["cargo_id"])
    state["conveyor"]["admissions"].sort(
        key=lambda a: (a["inlet"], a["ready_tick"], a["owner"], a["cargo_id"])
    )
    state["shipping"]["scanning"].sort(key=lambda scan: scan["actor_id"])


def _actor(actor: dict[str, Any], actions: list[dict[str, Any]], at_s: float, tps: int) -> None:
    index = bisect_right(actions, at_s, key=lambda action: action["start_s"]) - 1
    active = actions[index] if index >= 0 else None
    blocked = actor["state"] in {"BLOCKED", "WAIT_RESOURCE"}
    covered = active is not None and (
        active["end_s"] is None
        or active["end_s"] > at_s
        or ((blocked or active["open_ended"]) and active["end_s"] == at_s)
    )
    if active is not None and covered:
        blocked = active["state"] in {"BLOCKED", "WAIT_RESOURCE"}
    actor["action"] = dict(active) if active is not None and covered else None
    actor["blocked_since_tick"] = (
        active.get("blocked_since_tick", round(active["start_s"] * tps))
        if active is not None and covered and blocked
        else None
    )
    actor["carrying_cargo_id"] = active["carrying_cargo_id"] if active and covered else None
    if active and covered:
        actor["state"] = active["state"]
        actor["pos"] = position_at(active, at_s)


def position_at(action: dict[str, Any], at_s: float) -> list[float]:
    if "pos" in action:
        return list(action["pos"])
    points = action["waypoints"]
    index = bisect_right(points, at_s, key=lambda point: point["at_s"]) - 1
    left = points[max(index, 0)]
    if index >= len(points) - 1:
        return list(left["pos"])
    right = points[max(index + 1, 0)]
    duration = right["at_s"] - left["at_s"]
    part = (at_s - left["at_s"]) / duration if duration else 0
    return [a + (b - a) * part for a, b in zip(left["pos"], right["pos"], strict=True)]
