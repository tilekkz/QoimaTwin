"""Pinned actual-source compilation acceptance, independent stock literals."""

from pathlib import Path

import pytest

from app.storage.canonical_json import sha256_hex
from app.v3.execution import ManualEngine
from app.v3.materialize_manifest import materialized_bytes
from app.v3.profile import CompiledManualInputs, load_manual_profile

BUNDLE = Path(__file__).parents[2] / "data/v3-proposal"
PROPOSAL = Path(__file__).parents[2] / "data/v3-execution-proposals/manual-whole-hu-demo-v1.json"


@pytest.fixture(scope="module")
def compiled() -> CompiledManualInputs:
    return load_manual_profile(BUNDLE, PROPOSAL)


def test_actual_source_compiles_complete_stock_and_fixed_demo(
    compiled: CompiledManualInputs,
) -> None:
    result = compiled
    profile = result.profile
    assert len(profile.actors) == 24
    assert len(profile.initial_placements) == 530
    assert len({h.sku_id for h in profile.handling_units}) == 200
    assert len(profile.handling_units) == 532
    initial = {p.hu_id for p in profile.initial_placements}
    assert sum(h.quantity for h in profile.handling_units if h.hu_id in initial) == 12256
    assert len(profile.jobs) == 4
    assert [j.arrival_tick for j in profile.jobs] == [0, 0, 60_000_000, 60_000_000]
    assert result.horizon_tick == 600_000_000
    assert result.end_tick == 900_000_000
    assert all(b.node_id != p.service_node_id for p in profile.ports for b in p.buffer_places)
    with pytest.raises(AttributeError):
        profile.profile_id = "changed"  # type: ignore[misc]


def test_actual_source_demo_conserves_every_sku(compiled: CompiledManualInputs) -> None:
    engine = ManualEngine(compiled.profile, compiled.graph, check_invariants=True)
    outcome = engine.run(compiled.horizon_tick, compiled.end_tick)
    assert outcome.at_end.status == "complete"
    assert all(j.state == "complete" for j in outcome.at_end.jobs)
    assert sum(q for _, q in outcome.at_end.stock_units) == 12256
    assert sum(q for _, q in outcome.at_end.shipped_units) == 48
    assert not any(q for _, q in outcome.at_end.outside_units)
    assert not any(q for _, q in outcome.at_end.wip_units)
    assert not outcome.at_end.leases
    expected: dict[str, int] = {}
    for hu in compiled.profile.handling_units:
        expected[hu.sku_id] = expected.get(hu.sku_id, 0) + hu.quantity
    for snapshot in (outcome.at_horizon, outcome.at_end):
        actual: dict[str, int] = {}
        for ledger in (
            snapshot.stock_units,
            snapshot.wip_units,
            snapshot.outside_units,
            snapshot.shipped_units,
        ):
            for sku, quantity in ledger:
                actual[sku] = actual.get(sku, 0) + quantity
        assert actual == expected
    assert all(
        w.node_id == a.home_node_id and w.motion is None
        for w, a in zip(
            outcome.at_end.workers,
            sorted(compiled.profile.actors, key=lambda a: a.actor_id),
            strict=True,
        )
    )


def test_review_artifact_reproduces_frozen_inputs(compiled: CompiledManualInputs) -> None:
    artifact = PROPOSAL.with_name("manual-whole-hu-demo-v1.materialized.json")
    assert materialized_bytes(compiled) == artifact.read_bytes()
    graph_document = compiled.graph_document.decode()
    assert sha256_hex(graph_document) == compiled.graph.sha256
    assert len(graph_document["walk_graph"]["nodes"]) == 1640
    assert len(graph_document["walk_graph"]["arcs"]) == 4014
    graph_document["walk_graph"]["nodes"].clear()
    assert len(compiled.graph_document.decode()["walk_graph"]["nodes"]) == 1640
