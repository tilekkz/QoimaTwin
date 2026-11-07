"""Observed actor anchors and typed HU locations; never infer stock pose from an aisle node."""

from fractions import Fraction

from app.v3.interface import Json
from app.v3.run_replay import replay_manual
from app.v3.run_values import fraction


def actor_pose_at(run: Json, actor_id: str, cutoff_tick: int) -> Json:
    state = replay_manual(run, cutoff_tick)
    workers = {row["actor_id"]: row for row in state["workers"]}
    if actor_id not in workers:
        raise ValueError("manual pose has an unknown actor")
    worker = workers[actor_id]
    graph = run["graph_document"]["walk_graph"]
    nodes = {row["node_id"]: row["world_pos"] for row in graph["nodes"]}
    motion = worker["motion"]
    position = nodes[worker["node_id"]] if motion is None else _position(motion, graph, cutoff_tick)
    return {
        "actor_id": actor_id,
        "observed_tick": cutoff_tick,
        "world_pos": list(position),
        "anchor": "graph_route_anchor",
        "planned_end_tick": None if motion is None else motion["end_tick"],
        "carrying_hu_ids": sorted(
            row["hu_id"]
            for row in state["owners"]
            if row["kind"] == "worker" and row["location_id"] == actor_id
        ),
    }


def _position(motion: Json, graph: Json, tick: int) -> list[float]:
    start, end = motion["start_tick"], motion["end_tick"]
    if not start <= tick < end:
        raise ValueError("manual motion is not active at the observed tick")
    route = motion["route"]
    remaining = fraction(route["length_m"]) * Fraction(tick - start, end - start)
    nodes = {row["node_id"]: row["world_pos"] for row in graph["nodes"]}
    arcs = {row["arc_id"]: row for row in graph["arcs"]}
    for arc_id in route["arc_ids"]:
        arc = arcs[arc_id]
        length = Fraction(str(arc["length_m"]))
        if remaining <= length:
            a, b = nodes[arc["from_node_id"]], nodes[arc["to_node_id"]]
            ratio = remaining / length
            return [
                float(Fraction(str(x)) + (Fraction(str(y)) - Fraction(str(x))) * ratio)
                for x, y in zip(a, b, strict=True)
            ]
        remaining -= length
    raise ValueError("manual route has no segment at the observed distance")


def hu_location_at(run: Json, hu_id: str, cutoff_tick: int) -> Json:
    owners = {row["hu_id"]: row for row in replay_manual(run, cutoff_tick)["owners"]}
    if hu_id not in owners:
        raise ValueError("manual location has an unknown HU")
    owner = owners[hu_id]
    kinds = {
        "stock": ("storage_slot", "slot_id"),
        "worker": ("worker_attachment", "actor_id"),
        "buffer": ("buffer_place", "place_id"),
        "service": ("port_service", "port_id"),
        "shipped": ("shipped", "port_id"),
        "outside": ("outside", "location_id"),
        "unreleased": ("unreleased", "location_id"),
    }
    kind, key = kinds[owner["kind"]]
    return {"kind": kind, key: owner["location_id"], "hu_id": hu_id}
