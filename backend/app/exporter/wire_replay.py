"""Deterministic client-style replay; no callbacks, engine restore or future state access."""

import copy
from bisect import bisect_right
from itertools import groupby
from typing import Any

from app.exporter.replay_inventory import InventoryReplay
from app.exporter.replay_orders import apply_cells, apply_order
from app.exporter.replay_pallets import apply_pallet
from app.exporter.wire_positions import apply_position
from app.exporter.wire_snapshots import _actor, normalize_state, position_at
from app.storage.canonical_json import sha256_hex


def replay_snapshot(run: dict[str, Any], snapshot: dict[str, Any], at_tick: int) -> dict[str, Any]:
    if not snapshot["at_tick"] <= at_tick <= round(run["ended_at_s"] * run["ticks_per_second"]):
        raise ValueError("replay target is outside snapshot/run interval")
    state = copy.deepcopy(snapshot["state"])
    if sha256_hex(state) != snapshot["state_hash"]:
        raise ValueError("replay base state hash mismatch")
    inventory = InventoryReplay(state["ledger"])
    observation_actions = sorted(
        run["actions"] + run["boundary_actions"], key=lambda a: (a["start_s"], a["action_id"])
    )
    actions = {action["action_id"]: action for action in observation_actions}
    rows = [
        event
        for event in run["events"]
        if snapshot["last_seq"] < event["seq"] and event["at_tick"] <= at_tick
    ]
    params, known = run["replay_parameters"], set(run["conveyor_cells"])
    for _, grouped in groupby(rows, key=lambda event: (event["at_tick"], event["phase"])):
        group = list(grouped)
        moves = [event for event in group if event["kind"] == "cell_moved"]
        apply_cells(state, moves, params, known)
        for event in group:
            apply_position(state["placements"], event)
            inventory.apply(event)
            apply_order(state, event, params)
            apply_pallet(state, event, params, actions)
    inventory.write(state)
    _actors(state, observation_actions, at_tick, run["ticks_per_second"])
    normalize_state(state)
    return {
        "at_s": at_tick / run["ticks_per_second"],
        "at_tick": at_tick,
        "last_seq": rows[-1]["seq"] if rows else snapshot["last_seq"],
        "state_hash": sha256_hex(state),
        "state": state,
    }


def _actors(state: dict[str, Any], actions: list[dict[str, Any]], tick: int, tps: int) -> None:
    seconds = tick / tps
    for actor in state["actors"]:
        records = [action for action in actions if action["actor_id"] == actor["actor_id"]]
        index = bisect_right(records, seconds, key=lambda action: action["start_s"]) - 1
        if index >= 0:
            last = records[index]
            actor["pos"] = position_at(
                last, min(seconds, last["end_s"]) if last["end_s"] is not None else seconds
            )
        _actor(actor, records, seconds, tps)
