"""One outbound whole HU on a four-node hand graph; no source workload generation."""

from fractions import Fraction as F
from pathlib import Path

from app.storage.canonical_json import canonical_bytes, sha256_hex
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
from app.v3.input_models import ImmutableDocument
from app.v3.interface import Json
from app.v3.profile import CompiledManualInputs
from app.v3.runtime_graph_source import LAYOUT_VERSION, compiled_graph


def document() -> Json:
    return {
        "layout_version": LAYOUT_VERSION,
        "connector_provenance": {"kind": "synthetic_test_only"},
        "walk_graph": {
            "nodes": [
                {"node_id": n, "world_pos": [x, 0, 0]}
                for n, x in (("H", 0), ("P", 2), ("B", 5), ("S", 10))
            ],
            "arcs": [
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
            ],
        },
    }


def tiny_inputs(bundle: Path, proposal: Path) -> CompiledManualInputs:
    del bundle, proposal
    graph_doc = document()
    digest = sha256_hex(graph_doc)
    bound = BoundGraph(compiled_graph(graph_doc, "walk"), LAYOUT_VERSION, digest)
    actors = tuple(
        ActorSpec(a, "H", frozenset({"ship"}) if a == "R01" else frozenset(), F(1), F(15))
        for a in ACTOR_IDS
    )
    slot = PlaceSpec("SLOT", "S", (F(1),) * 3, F(15), frozenset({"SMALL_CARTON"}))
    buffer = PlaceSpec("BUFFER", "B", (F(1),) * 3, F(15), slot.allowed_archetypes)
    port = PortSpec(
        "PORT",
        "outbound",
        "P",
        (buffer,),
        (("SMALL_CARTON", 1000000),),
        ((0, 100000000),),
        frozenset({"R01"}),
    )
    hu = HandlingUnit("HU", "SKU", 24, "SMALL_CARTON", F(3), (F(1, 5),) * 3)
    profile = ExecutionProfile(
        "tiny-benchmark-protocol-test",
        LAYOUT_VERSION,
        digest,
        (SourceBinding("test", "1" * 64),),
        actors,
        (port,),
        (slot,),
        (hu,),
        (InitialPlacement("HU", "SLOT"),),
        (TimedJob("JOB", 0, "outbound", "HU", "PORT", "SLOT"),),
        HandlingTimes(1000000, 1000000),
        "test only",
    )
    return CompiledManualInputs(
        profile,
        bound,
        60000000,
        90000000,
        sha256_hex("tiny"),
        ImmutableDocument(canonical_bytes(graph_doc)),
    )
