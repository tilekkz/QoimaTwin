"""Explicit synthetic input builders, independent of production source compilation."""

from dataclasses import dataclass, replace
from fractions import Fraction as F

from app.v3.execution_types import (
    ACTOR_IDS,
    ActorSpec,
    BoundGraph,
    ExecutionProfile,
    HandlingTimes,
    HandlingUnit,
    InitialPlacement,
    PlaceSpec,
    PortSpec,
    SourceBinding,
    TimedJob,
)
from app.v3.runtime_graph import Arc, DirectedGraph


def ticks(seconds: int) -> int:
    return seconds * 1_000_000


@dataclass(frozen=True)
class ManualFixture:
    profile: ExecutionProfile
    graph: BoundGraph
    arcs: tuple[Arc, ...]


def graph_arcs() -> tuple[Arc, ...]:
    pairs = [("H", f"P{j}", j) for j in (1, 2, 3)]
    pairs += [(f"P{j}", f"B{j}", 1) for j in (1, 2, 3)]
    pairs += [(f"B{j}", f"S{j}", 2) for j in (1, 2, 3)]
    return tuple(
        Arc(f"{source}>{target}", source, target, F(length), F(length), frozenset({"pedestrian"}))
        for start, end, length in pairs
        for source, target in ((start, end), (end, start))
    )


def place(place_id: str, node: str) -> PlaceSpec:
    return PlaceSpec(place_id, node, (F(1), F(1), F(1)), F(15), frozenset({"SMALL_CARTON"}))


def ports() -> tuple[PortSpec, ...]:
    return tuple(
        PortSpec(
            f"port{j}",
            "inbound",
            f"P{j}",
            (place(f"buffer{j}", f"B{j}"),),
            (("SMALL_CARTON", ticks(2)),),
            ((0, ticks(100)),),
            frozenset({"R01", "R02"}),
        )
        for j in (1, 2, 3)
    )


def fixture(port_numbers: tuple[int, ...] = (1, 2, 3), arrival_s: int = 0) -> ManualFixture:
    actors = tuple(
        ActorSpec(
            actor,
            "H",
            frozenset({"receive"}) if actor in ("R01", "R02") else frozenset(),
            F(1),
            F(15),
        )
        for actor in ACTOR_IDS
    )
    hus = tuple(
        HandlingUnit(f"HU{i}", "SKU", 24, "SMALL_CARTON", F(1), (F(".2"),) * 3)
        for i in range(1, len(port_numbers) + 1)
    )
    slots = tuple(place(f"slot{i}", f"S{j}") for i, j in enumerate(port_numbers, 1))
    jobs = tuple(
        TimedJob(f"J{i}", ticks(arrival_s), "inbound", f"HU{i}", f"port{j}", f"slot{i}")
        for i, j in enumerate(port_numbers, 1)
    )
    arcs = graph_arcs()
    nodes = ("H", *(f"{prefix}{j}" for prefix in ("P", "B", "S") for j in (1, 2, 3)))
    graph = BoundGraph(DirectedGraph("walk", nodes, arcs), "hand-v3", "a" * 64)
    profile = ExecutionProfile(
        "independent-manual-oracle",
        "hand-v3",
        "a" * 64,
        (SourceBinding("synthetic-hand-fixture", "b" * 64),),
        actors,
        ports(),
        slots,
        hus,
        (),
        jobs,
        HandlingTimes(ticks(1), ticks(1)),
        "Independent hand arithmetic; not a production execution profile",
    )
    return ManualFixture(profile, graph, arcs)


def business_fixture(direction: str) -> ManualFixture:
    data = fixture((1,))
    lengths = {frozenset({"H", "P1"}): 2, frozenset({"P1", "B1"}): 3, frozenset({"B1", "S1"}): 5}
    arcs = tuple(
        replace(
            arc,
            length_m=F(lengths[frozenset({arc.source, arc.target})]),
            cost_m=F(lengths[frozenset({arc.source, arc.target})]),
        )
        if frozenset({arc.source, arc.target}) in lengths
        else arc
        for arc in data.arcs
    )
    graph = replace(data.graph, graph=DirectedGraph("walk", data.graph.graph.node_ids, arcs))
    skill = "receive" if direction == "inbound" else "ship"
    actors = tuple(
        replace(actor, skills=frozenset({skill}) if actor.actor_id == "R01" else frozenset())
        for actor in data.profile.actors
    )
    port = replace(
        data.profile.ports[0], direction=direction, service_ticks=(("SMALL_CARTON", ticks(10)),)
    )
    jobs = (replace(data.profile.jobs[0], direction=direction),)
    initial = () if direction == "inbound" else (InitialPlacement("HU1", "slot1"),)
    profile = replace(
        data.profile, actors=actors, ports=(port,), jobs=jobs, initial_placements=initial
    )
    return ManualFixture(profile, graph, arcs)
