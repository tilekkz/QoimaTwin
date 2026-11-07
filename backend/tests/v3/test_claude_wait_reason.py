"""Claude review: a bay/slot lease conflict must be reported as a resource wait (ADR 0031/0034).

Hand graph (both directions declared): H-P 2 m, P-B 3 m, B-S 5 m, plus an isolated node X.
Three receivers, one at X (no route) and two at H; speed 1 m/s, intake 10 s.
Hand arithmetic: j1 takes the first routable receiver, pays approach 2 s and holds the inbound
bay until service end 2 + 10 = 12 s. j2 has a feasible route and window via the other H
receiver, but the bay is leased, so it waits for resources on [0, 12). The X receiver's
missing route is not the reason.
"""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.execution import ManualEngine
from app.v3.execution_types import (
    BoundGraph,
    ExecutionProfile,
    HandlingUnit,
    JobView,
    TimedJob,
)
from app.v3.runtime_graph import DirectedGraph
from tests.v3.test_execution_manual import fixture, tick


def _profile(homes: dict[str, str]) -> tuple[ExecutionProfile, BoundGraph]:
    profile, bound = fixture("inbound")
    graph = bound.graph
    isolated = DirectedGraph("walk", (*graph.node_ids, "X"), graph.arcs)
    actors = tuple(
        replace(a, home_node_id=homes[a.actor_id], skills=frozenset({"receive"}))
        if a.actor_id in homes
        else a
        for a in profile.actors
    )
    port = profile.ports[0]
    buffers = tuple(replace(port.buffer_places[0], place_id=f"b{i}") for i in (1, 2))
    port = replace(port, buffer_places=buffers, eligible_actor_ids=frozenset(homes))
    slots = tuple(replace(profile.slots[0], place_id=f"s{i}") for i in (1, 2))
    hu = profile.handling_units[0]
    units = (
        hu,
        HandlingUnit("HU2", hu.sku_id, hu.quantity, hu.archetype, F(1), hu.dimensions_xyz_m),
    )
    jobs = tuple(
        TimedJob(f"j{i}", 0, "inbound", unit.hu_id, "port", f"s{i}")
        for i, unit in enumerate(units, start=1)
    )
    changed = replace(
        profile, actors=actors, ports=(port,), slots=slots, handling_units=units, jobs=jobs
    )
    return changed, replace(bound, graph=isolated)


@pytest.mark.parametrize(
    "homes",
    [
        {"R01": "X", "R02": "H", "S01": "H"},  # unroutable candidate sorts first
        {"R01": "H", "R02": "H", "S02": "X"},  # unroutable candidate sorts last
    ],
)
def test_lease_conflict_with_an_unroutable_candidate_is_a_resource_wait(
    homes: dict[str, str],
) -> None:
    profile, graph = _profile(homes)
    result = ManualEngine(profile, graph, check_invariants=True).run(tick(500), tick(900))
    views: list[tuple[int, JobView]] = [
        (e.tick, e.job) for e in result.events if e.job is not None and e.job.job_id == "j2"
    ]
    waiting = [(t, v.wait_reason) for t, v in views if v.state == "waiting"]
    assert waiting[-1] == (tick(0), "resources")
    assert "no_route" not in {reason for _, reason in waiting}
    assert result.at_end.status == "complete"
