"""Hand-written observations isolate serialization/replay from the execution scheduler."""

from dataclasses import replace
from fractions import Fraction as F

from app.storage.canonical_json import sha256_hex
from app.v3.execution_types import (
    ACTOR_IDS,
    ActorSpec,
    BoundGraph,
    ExecutionProfile,
    HandlingTimes,
    HandlingUnit,
    HUOwner,
    InitialPlacement,
    ManualOutcome,
    ManualSnapshot,
    PlaceSpec,
    PortSpec,
    SourceBinding,
    TimedJob,
    WorkerView,
)
from app.v3.interface import LAYOUT_VERSION, Json
from app.v3.runtime_graph_source import compiled_graph


def graph_document() -> Json:
    return {
        "layout_version": LAYOUT_VERSION,
        "walk_graph": {
            "nodes": [
                {"node_id": "H", "world_pos": [1, 0, 1]},
                {"node_id": "S", "world_pos": [4, 0, 1]},
            ],
            "arcs": [
                {
                    "arc_id": a + b,
                    "from_node_id": a,
                    "to_node_id": b,
                    "length_m": 3,
                    "cost_m": 3,
                    "allowed_modes": ["pedestrian"],
                }
                for a, b in (("H", "S"), ("S", "H"))
            ],
        },
        "connector_provenance": {"kind": "synthetic_hand_fixture", "source": "two-node line"},
    }


def empty_run_inputs() -> tuple[ExecutionProfile, BoundGraph, ManualOutcome, Json]:
    document = graph_document()
    digest = sha256_hex(document)
    graph = BoundGraph(compiled_graph(document, "walk"), LAYOUT_VERSION, digest)
    actors = tuple(ActorSpec(a, "H", frozenset(), F(13, 10), F(15)) for a in ACTOR_IDS)
    slot = PlaceSpec("SLOT", "S", (F(1),) * 3, F(15), frozenset({"SMALL_CARTON"}))
    hu = HandlingUnit("HU1", "SKU1", 24, "SMALL_CARTON", F(7, 2), (F(1, 5),) * 3)
    profile = ExecutionProfile(
        "hand-static-observation",
        LAYOUT_VERSION,
        digest,
        (SourceBinding("fixture", "1" * 64),),
        actors,
        (),
        (slot,),
        (hu,),
        (InitialPlacement("HU1", "SLOT"),),
        (),
        HandlingTimes(1_000_000, 1_000_000),
        "Synthetic serialization test; no operational claim",
    )
    workers = tuple(WorkerView(a, "H", None, None) for a in sorted(ACTOR_IDS))
    state = ManualSnapshot(
        0,
        "complete",
        (),
        workers,
        (HUOwner("HU1", "stock", "SLOT"),),
        (),
        (("SKU1", 24),),
        (),
        (),
        (),
    )
    return profile, graph, ManualOutcome(profile.profile_id, (), state, state), document


def manual_profile(direction: str = "inbound") -> tuple[ExecutionProfile, BoundGraph, Json]:
    base, _, _, document = empty_run_inputs()
    positions = {"H": 0, "P": 2, "B": 5, "S": 10}
    document["walk_graph"]["nodes"] = [
        {"node_id": node, "world_pos": [x, 0, 0]} for node, x in positions.items()
    ]
    document["walk_graph"]["arcs"] = [
        {
            "arc_id": a + b,
            "from_node_id": a,
            "to_node_id": b,
            "length_m": length,
            "cost_m": length,
            "allowed_modes": ["pedestrian"],
        }
        for a, b, length in (("H", "P", 2), ("P", "B", 3), ("B", "S", 5))
        for a, b in ((a, b), (b, a))
    ]
    digest = sha256_hex(document)
    graph = BoundGraph(compiled_graph(document, "walk"), LAYOUT_VERSION, digest)
    skill = "receive" if direction == "inbound" else "ship"
    actors = tuple(
        replace(
            a, speed_m_s=F(1), skills=frozenset({skill}) if a.actor_id == "R01" else frozenset()
        )
        for a in base.actors
    )
    buffer = replace(base.slots[0], place_id="BUFFER", node_id="B")
    port = PortSpec(
        "PORT",
        direction,
        "P",
        (buffer,),
        (("SMALL_CARTON", 10_000_000),),
        ((0, 1000_000_000),),
        frozenset({"R01"}),
    )
    profile = replace(
        base,
        graph_sha256=digest,
        actors=actors,
        ports=(port,),
        jobs=(TimedJob("JOB", 0, direction, "HU1", "PORT", "SLOT"),),
        initial_placements=() if direction == "inbound" else base.initial_placements,
    )
    return profile, graph, document
