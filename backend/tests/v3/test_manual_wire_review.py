"""Independent corruption probes for the manual event and finite-resource contract."""

from dataclasses import replace

import pytest

from app.storage.canonical_json import sha256_hex
from app.v3.execution import ManualEngine
from app.v3.execution_types import BoundGraph
from app.v3.run_export import build_manual_run
from app.v3.runtime_graph_source import LAYOUT_VERSION, compiled_graph
from tests.v3.test_manual_acceptance_fixtures import fixture, ticks
from tests.v3.test_manual_acceptance_replay import graph_document


@pytest.mark.parametrize(
    ("resource", "replacement"),
    [
        ("port:port1", "port:nonexistent"),
        ("buffer:buffer1", "buffer:nonexistent"),
        ("slot:slot1", "slot:nonexistent"),
        ("hu:HU1", "hu:nonexistent"),
        ("worker:R01", "worker:nonexistent"),
        ("port:port1", "port:port3"),
        ("buffer:buffer1", "buffer:buffer3"),
        ("slot:slot1", "slot:slot3"),
        ("hu:HU1", "hu:HU3"),
        ("worker:R01", "worker:P01"),
    ],
)
def test_matched_leases_for_wrong_finite_resource_are_rejected(
    resource: str,
    replacement: str,
) -> None:
    data = fixture()
    document = graph_document(data)
    digest = sha256_hex(document)
    profile = replace(data.profile, layout_version=LAYOUT_VERSION, graph_sha256=digest)
    graph = BoundGraph(compiled_graph(document, "walk"), LAYOUT_VERSION, digest)
    outcome = ManualEngine(profile, graph, check_invariants=True).run(ticks(40), ticks(50))
    events = tuple(
        replace(event, resource_ids=(replacement,)) if resource in event.resource_ids else event
        for event in outcome.events
    )
    forged = replace(outcome, events=events)
    with pytest.raises(ValueError):
        build_manual_run(
            profile,
            graph,
            forged,
            graph_document=document,
            end_tick_limit=ticks(50),
            snapshot_interval_ticks=ticks(7),
        )


@pytest.mark.parametrize("kind", ["worker", "buffer", "port"])
def test_operations_without_required_exclusive_leases_are_rejected(kind: str) -> None:
    data = fixture()
    document = graph_document(data)
    digest = sha256_hex(document)
    profile = replace(data.profile, layout_version=LAYOUT_VERSION, graph_sha256=digest)
    graph = BoundGraph(compiled_graph(document, "walk"), LAYOUT_VERSION, digest)
    outcome = ManualEngine(profile, graph, check_invariants=True).run(ticks(40), ticks(50))
    kept = [
        event
        for event in outcome.events
        if not any(resource.startswith(kind + ":") for resource in event.resource_ids)
    ]
    forged = replace(
        outcome, events=tuple(replace(event, seq=seq) for seq, event in enumerate(kept))
    )
    with pytest.raises(ValueError):
        build_manual_run(
            profile,
            graph,
            forged,
            graph_document=document,
            end_tick_limit=ticks(50),
            snapshot_interval_ticks=ticks(7),
        )
