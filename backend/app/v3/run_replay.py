"""Reconstruct observations from typed manual events, without resuming an engine."""

from collections import Counter
from copy import deepcopy

from app.v3.interface import Json


def initial_state(profile: Json) -> Json:
    placements = {row["hu_id"]: row["slot_id"] for row in profile["initial_placements"]}
    state = {
        "tick": 0,
        "status": "partial",
        "leases": [],
        "jobs": [
            {
                "job_id": row["job_id"],
                "state": "unreleased",
                "wait_reason": "not_arrived",
                "actor_id": None,
            }
            for row in profile["jobs"]
        ],
        "workers": [
            {
                "actor_id": row["actor_id"],
                "node_id": row["home_node_id"],
                "motion": None,
                "job_id": None,
            }
            for row in profile["actors"]
        ],
        "owners": [
            {
                "hu_id": row["hu_id"],
                "kind": "stock" if row["hu_id"] in placements else "unreleased",
                "location_id": placements.get(row["hu_id"], "outside"),
            }
            for row in profile["handling_units"]
        ],
    }
    settle(state, profile, 0)
    return state


def _replace(rows: list[Json], key: str, value: Json) -> None:
    for index, row in enumerate(rows):
        if row[key] == value[key]:
            rows[index] = deepcopy(value)
            return
    raise ValueError(f"manual event refers to unknown {key}")


def apply_event(state: Json, event: Json) -> None:
    for field, section, key in (
        ("job", "jobs", "job_id"),
        ("worker", "workers", "actor_id"),
        ("owner", "owners", "hu_id"),
    ):
        if event[field] is not None:
            _replace(state[section], key, event[field])
    if event["kind"] not in {"lease_acquired", "lease_released"}:
        return
    leases = {row["resource_id"]: row for row in state["leases"]}
    for resource in event["resource_ids"]:
        if event["kind"] == "lease_acquired":
            if resource in leases:
                raise ValueError("manual replay duplicate lease")
            leases[resource] = {
                "resource_id": resource,
                "job_id": event["job_id"],
                "acquired_tick": event["tick"],
            }
        else:
            if resource not in leases or leases[resource]["job_id"] != event["job_id"]:
                raise ValueError("manual replay release lacks matching lease")
            del leases[resource]
    state["leases"] = list(leases.values())


def settle(state: Json, profile: Json, tick: int) -> None:
    state["tick"] = tick
    state["status"] = (
        "complete" if all(j["state"] == "complete" for j in state["jobs"]) else "partial"
    )
    for section, key in (
        ("jobs", "job_id"),
        ("workers", "actor_id"),
        ("owners", "hu_id"),
        ("leases", "resource_id"),
    ):
        state[section].sort(key=lambda row: row[key])
    owners = {row["hu_id"]: row["kind"] for row in state["owners"]}
    for key, kinds in (
        ("stock_units", {"stock"}),
        ("wip_units", {"worker", "buffer", "service"}),
        ("outside_units", {"outside"}),
        ("shipped_units", {"shipped"}),
    ):
        quantities: Counter[str] = Counter()
        for hu in profile["handling_units"]:
            if owners[hu["hu_id"]] in kinds:
                quantities[hu["sku_id"]] += hu["quantity"]
        state[key] = [[sku, quantity] for sku, quantity in sorted(quantities.items())]


def replay_manual(run: Json, cutoff_tick: int) -> Json:
    if type(cutoff_tick) is not int or not 0 <= cutoff_tick <= run["observed_until_tick"]:
        raise ValueError("manual replay cutoff is outside the observed timeline")
    eligible = [item for item in run["snapshots"] if item["tick"] <= cutoff_tick]
    checkpoint = max(eligible, key=lambda item: item["tick"]) if eligible else None
    state: Json = deepcopy(checkpoint["state"] if checkpoint else run["initial_state"])
    through = checkpoint["through_seq"] if checkpoint else -1
    for event in run["events"]:
        if through < event["seq"] and event["tick"] <= cutoff_tick:
            apply_event(state, event)
    settle(state, run["profile"], cutoff_tick)
    return state
