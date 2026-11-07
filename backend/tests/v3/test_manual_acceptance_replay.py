"""Actual three-HU execution replay against independent hand counts and graph bytes."""

from copy import deepcopy
from dataclasses import replace
from typing import Any

from app.storage.canonical_json import sha256_hex
from app.v3.execution import ManualEngine
from app.v3.execution_types import BoundGraph
from app.v3.run_export import build_manual_run
from app.v3.run_replay import replay_manual
from app.v3.runtime_graph_source import LAYOUT_VERSION, compiled_graph
from tests.v3.test_manual_acceptance_fixtures import ManualFixture, fixture, ticks


def graph_document(data: ManualFixture) -> dict[str, Any]:
    positions = {
        "H": [10, 0, 10],
        "P1": [11, 0, 10],
        "B1": [12, 0, 10],
        "S1": [14, 0, 10],
        "P2": [10, 0, 12],
        "B2": [10, 0, 13],
        "S2": [10, 0, 15],
        "P3": [7, 0, 10],
        "B3": [6, 0, 10],
        "S3": [4, 0, 10],
    }
    return {
        "layout_version": LAYOUT_VERSION,
        "connector_provenance": {
            "kind": "synthetic_hand_fixture",
            "source": "independent manual acceptance hub",
        },
        "walk_graph": {
            "nodes": [
                {"node_id": node, "world_pos": positions[node]}
                for node in data.graph.graph.node_ids
            ],
            "arcs": [
                {
                    "arc_id": arc.arc_id,
                    "from_node_id": arc.source,
                    "to_node_id": arc.target,
                    "length_m": int(arc.length_m),
                    "cost_m": int(arc.cost_m),
                    "allowed_modes": ["pedestrian"],
                }
                for arc in data.arcs
            ],
        },
    }


def test_three_hu_seek_10_28_5_28_is_repeatable_without_stock_duplication() -> None:
    data = fixture()
    document = graph_document(data)
    digest = sha256_hex(document)
    profile = replace(data.profile, layout_version=LAYOUT_VERSION, graph_sha256=digest)
    graph = BoundGraph(compiled_graph(document, "walk"), LAYOUT_VERSION, digest)
    outcome = ManualEngine(profile, graph, check_invariants=True).run(ticks(25), ticks(40))
    run = build_manual_run(
        profile,
        graph,
        outcome,
        graph_document=document,
        end_tick_limit=ticks(40),
        snapshot_interval_ticks=ticks(7),
    )
    before = deepcopy(run)
    a, b, c, d = [replay_manual(run, ticks(second)) for second in (10, 28, 5, 28)]
    assert a["stock_units"] == [["SKU", 48]]
    assert a["outside_units"] == [["SKU", 24]]
    assert b["stock_units"] == [["SKU", 72]]
    assert b["wip_units"] == b["outside_units"] == []
    assert c["stock_units"] == []
    assert c["wip_units"] == [["SKU", 48]]
    assert c["outside_units"] == [["SKU", 24]]
    assert b == d
    assert run == before
    for state in (a, b, c, d):
        assert len(state["owners"]) == len({row["hu_id"] for row in state["owners"]}) == 3
        assert (
            sum(
                quantity
                for key in ("stock_units", "wip_units", "outside_units", "shipped_units")
                for _, quantity in state[key]
            )
            == 72
        )
