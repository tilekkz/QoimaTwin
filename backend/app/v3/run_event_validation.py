"""Typed transition and actual route checks supplement JSON shape and content hashes."""

from app.v3.interface import Json
from app.v3.run_values import fraction
from app.v3.runtime_graph import DirectedGraph
from app.v3.runtime_time import travel_ticks


def validate_events(run: Json, graph: DirectedGraph) -> None:
    profile = run["profile"]
    jobs = {row["job_id"]: row for row in profile["jobs"]}
    actors = {row["actor_id"]: row for row in profile["actors"]}
    units = {row["hu_id"]: row for row in profile["handling_units"]}
    ports = {row["port_id"]: row for row in profile["ports"]}
    workers = {row["actor_id"]: row for row in run["initial_state"]["workers"]}
    for event in run["events"]:
        if event["job_id"] not in jobs or event["hu_id"] != jobs[event["job_id"]]["hu_id"]:
            raise ValueError("manual event has an unknown job/HU reference")
        if event["actor_id"] is not None and event["actor_id"] not in actors:
            raise ValueError("manual event has an unknown actor")
        if event["actor_id"] is not None:
            job = jobs[event["job_id"]]
            _capability(
                actors[event["actor_id"]], units[event["hu_id"]], ports[job["port_id"]], job
            )
        _payload(event)
        if event["job"] is not None and event["job"]["job_id"] != event["job_id"]:
            raise ValueError("manual job transition identity mismatch")
        if event["owner"] is not None:
            _owner(event, profile)
        if event["motion"] is not None:
            _motion(event["motion"], graph, actors[event["actor_id"]], event["tick"])
        if event["worker"] is not None:
            _worker(event, graph, actors, workers)


def _capability(actor: Json, unit: Json, port: Json, job: Json) -> None:
    skill = "receive" if job["direction"] == "inbound" else "ship"
    if actor["actor_id"] not in port["eligible_actor_ids"] or skill not in actor["skills"]:
        raise ValueError("manual executed job requires an eligible actor with the actual skill")
    if fraction(unit["gross_mass_kg"]) > fraction(actor["max_gross_mass_kg"]):
        raise ValueError("manual executed load exceeds the actual actor capacity")


def _payload(event: Json) -> None:
    for kind, field in (
        ("job_changed", "job"),
        ("worker_changed", "worker"),
        ("hu_owner_changed", "owner"),
    ):
        if (event["kind"] == kind) != (event[field] is not None):
            raise ValueError(f"manual {kind} requires its typed payload exclusively")
    lease = event["kind"] in {"lease_acquired", "lease_released"}
    if len(event["resource_ids"]) != int(lease):
        raise ValueError("manual lease event requires exactly one resource")
    operation = event["kind"] in {"operation_started", "operation_completed"}
    if operation != (event["stage"] is not None and event["location_id"] is not None):
        raise ValueError("manual operation requires stage and location")
    if event["motion"] is not None and event["kind"] != "operation_started":
        raise ValueError("only a started operation may announce planned motion")


def _owner(event: Json, profile: Json) -> None:
    owner = event["owner"]
    if owner["hu_id"] != event["hu_id"]:
        raise ValueError("manual HU transition identity mismatch")
    references = {
        "stock": {row["place_id"] for row in profile["slots"]},
        "worker": {row["actor_id"] for row in profile["actors"]},
        "buffer": {row["place_id"] for port in profile["ports"] for row in port["buffer_places"]},
        "service": {row["port_id"] for row in profile["ports"]},
        "shipped": {row["port_id"] for row in profile["ports"]},
        "outside": {"outside"},
        "unreleased": {"outside"},
    }
    if owner["location_id"] not in references[owner["kind"]]:
        raise ValueError("manual HU owner has an unknown location")


def _motion(motion: Json, graph: DirectedGraph, actor: Json, tick: int) -> None:
    route = motion["route"]
    nodes, arc_ids = route["node_ids"], route["arc_ids"]
    if route["graph_id"] != graph.graph_id or len(nodes) != len(arc_ids) + 1:
        raise ValueError("manual motion route has an invalid graph/path shape")
    if any(node not in graph.node_ids for node in nodes):
        raise ValueError("manual motion has an unknown graph node")
    arcs = {arc.arc_id: arc for arc in graph.arcs}
    if any(arc_id not in arcs for arc_id in arc_ids):
        raise ValueError("manual motion has an unknown directed arc")
    chosen = [arcs[arc_id] for arc_id in arc_ids]
    if any((arc.source, arc.target) != (nodes[i], nodes[i + 1]) for i, arc in enumerate(chosen)):
        raise ValueError("manual motion cannot infer a reverse arc")
    if any("pedestrian" not in arc.modes for arc in chosen):
        raise ValueError("manual motion uses an arc without pedestrian permission")
    if sum(arc.length_m for arc in chosen) != fraction(route["length_m"]):
        raise ValueError("manual motion length differs from its actual directed arcs")
    if sum(arc.cost_m for arc in chosen) != fraction(route["cost_m"]):
        raise ValueError("manual motion cost differs from its actual directed arcs")
    duration = travel_ticks(fraction(route["length_m"]), fraction(actor["speed_m_s"]))
    if motion["start_tick"] != tick or motion["end_tick"] != tick + duration:
        raise ValueError("manual planned motion must use the declared exact operation clock")


def _worker(event: Json, graph: DirectedGraph, actors: Json, workers: Json) -> None:
    worker = event["worker"]
    actor = worker["actor_id"]
    if actor != event["actor_id"] or actor not in actors:
        raise ValueError("manual worker transition identity mismatch")
    if worker["job_id"] not in {None, event["job_id"]}:
        raise ValueError("manual worker job reference mismatch")
    previous, motion = workers[actor], worker["motion"]
    if (motion is None) == (worker["node_id"] is None):
        raise ValueError("manual worker requires either a node or planned motion")
    if motion is not None:
        _motion(motion, graph, actors[actor], event["tick"])
        if previous["motion"] is not None or previous["node_id"] != motion["route"]["node_ids"][0]:
            raise ValueError("manual worker motion would teleport from its observed position")
    elif previous["motion"] is not None:
        planned = previous["motion"]
        if (
            event["tick"] != planned["end_tick"]
            or worker["node_id"] != planned["route"]["node_ids"][-1]
        ):
            raise ValueError("manual completed motion differs from its planned destination/time")
    elif worker["node_id"] != previous["node_id"]:
        raise ValueError("manual worker cannot change node without observed motion")
    workers[actor] = worker
