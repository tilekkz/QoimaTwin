"""Cross-reference and boundary integrity beyond structural schema validation."""

from bisect import bisect_right
from itertools import groupby
from typing import Any


def validate_integrity(run: dict[str, Any]) -> None:
    identity = run["identity"]
    keys = ("engine_version", "ticks_per_second", "horizon_s", "scenario_id", "experiment_type")
    if (
        any(identity.get(key) != run[key] for key in keys)
        or identity.get("hashes") != run["input_hashes"]
    ):
        raise ValueError("run identity metadata mismatch")
    if identity.get("wire_version") != "2.1-proposal":
        raise ValueError("run identity wire version mismatch")
    actors = {actor["actor_id"] for actor in run["actors"]}
    cargo = {item["cargo_id"] for item in run["cargo"]}
    all_actions = run["actions"] + run["boundary_actions"]
    actions = {action["action_id"]: action for action in all_actions}
    if len(actions) != len(all_actions):
        raise ValueError("duplicate action identity")
    for action in all_actions:
        if action["actor_id"] not in actors:
            raise ValueError("unknown action actor")
        if action["carrying_cargo_id"] is not None and action["carrying_cargo_id"] not in cargo:
            raise ValueError("unknown carried cargo")
    for action in run["boundary_actions"]:
        if action["start_s"] != run["ended_at_s"]:
            raise ValueError("boundary action is outside the run cutoff")
    for event in run["events"]:
        _event(event, actions, cargo)
    _snapshots(run, actions)
    _cells(run)
    _pre_shift(run, actors)


def _pre_shift(run: dict[str, Any], actors: set[str]) -> None:
    track = run["pre_shift"]
    if track is None:
        if run["relocation_plan_id"] is not None:
            raise ValueError("relocation plan has no pre-shift track")
        return
    if run["relocation_plan_id"] != run["input_hashes"]["relocation_plan"]:
        raise ValueError("relocation plan identity mismatch")
    if track["actor_id"] in actors:
        raise ValueError("relocation actor must be separate from shift roster")
    end = 0
    for action in track["actions"]:
        if not end <= action["start_tick"] < action["end_tick"] <= track["window_ticks"]:
            raise ValueError("overlapping or out-of-window pre-shift action")
        if action["actor_id"] != track["actor_id"]:
            raise ValueError("unknown pre-shift action actor")
        end = action["end_tick"]


def _event(event: dict[str, Any], actions: dict[str, Any], cargo: set[str]) -> None:
    p = event["payload"]
    for key in ("cargo_id", "tote_id", "parcel_id", "pallet_id"):
        if key in p and p[key] not in cargo:
            raise ValueError(f"unknown cargo reference: {p[key]}")
    if event["kind"] == "actor_state_changed" and p["action_id"] is not None:
        action = actions.get(p["action_id"])
        if action is None or action["actor_id"] != p["actor_id"] or action["state"] != p["state"]:
            raise ValueError("unknown or mismatched actor action reference")


def _snapshots(run: dict[str, Any], actions: dict[str, Any]) -> None:
    ticks = [event["at_tick"] for event in run["events"]]
    for snapshot in run["snapshots"]:
        if snapshot["last_seq"] != bisect_right(ticks, snapshot["at_tick"]) - 1:
            raise ValueError("snapshot event watermark mismatch")
        if snapshot["at_s"] != snapshot["at_tick"] / run["ticks_per_second"]:
            raise ValueError("snapshot timebase mismatch")
        for actor in snapshot["state"]["actors"]:
            action = actor["action"]
            if action is not None and (
                action["action_id"] not in actions or action != actions[action["action_id"]]
            ):
                raise ValueError("snapshot action differs from authoritative action")
            if actor["state"] in {"BLOCKED", "WAIT_RESOURCE"} and action is None:
                raise ValueError("blocked actor has no covering action")


def _cells(run: dict[str, Any]) -> None:
    known, occupancy = set(run["conveyor_cells"]), dict(run["initial_state"]["cells"])
    for _, events in groupby(run["events"], key=lambda e: (e["at_tick"], e["phase"])):
        moves = [event["payload"] for event in events if event["kind"] == "cell_moved"]
        for move in moves:
            if move["from"] in known and occupancy.pop(move["from"], None) != move["cargo_id"]:
                raise ValueError("cell source cargo mismatch")
        for move in moves:
            if move["to"] in known:
                if move["to"] in occupancy:
                    raise ValueError("atomic cell collision")
                occupancy[move["to"]] = move["cargo_id"]
