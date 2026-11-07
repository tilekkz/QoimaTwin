"""Independent timeline arithmetic for the explicit whole-HU manual proposal."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.execution import ManualEngine
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
from app.v3.runtime_time import operation_ticks


def tick(seconds: int) -> int:
    return operation_ticks(seconds)


def fixture(direction: str = "inbound") -> tuple[ExecutionProfile, BoundGraph]:
    # H--2m--P--3m--B--5m--S, both directions declared independently.
    nodes = ("H", "P", "B", "S")
    arcs = tuple(
        Arc(f"{a}:{b}", a, b, F(length), F(length), frozenset({"pedestrian"}))
        for a, b, length in (("H", "P", 2), ("P", "B", 3), ("B", "S", 5))
        for a, b in ((a, b), (b, a))
    )
    graph = BoundGraph(DirectedGraph("walk", nodes, arcs), "test-v3", "1" * 64)
    skill = "receive" if direction == "inbound" else "ship"
    actors = tuple(
        ActorSpec(a, "H", frozenset({skill}) if a == "R01" else frozenset(), F(1), F(15))
        for a in ACTOR_IDS
    )
    buffer = PlaceSpec("buffer", "B", (F(1), F(1), F(1)), F(15), frozenset({"SMALL_CARTON"}))
    slot = replace(buffer, place_id="slot", node_id="S")
    port = PortSpec(
        "port",
        direction,
        "P",
        (buffer,),
        (("SMALL_CARTON", tick(10)),),
        ((0, tick(1000)),),
        frozenset({"R01"}),
    )
    hu = HandlingUnit("HU1", "SKU1", 24, "SMALL_CARTON", F(1), (F(".2"),) * 3)
    initial = () if direction == "inbound" else (InitialPlacement("HU1", "slot"),)
    profile = ExecutionProfile(
        "manual-test",
        "test-v3",
        "1" * 64,
        (SourceBinding("fixture", "2" * 64),),
        actors,
        (port,),
        (slot,),
        (hu,),
        initial,
        (TimedJob("job1", 0, direction, "HU1", "port", "slot"),),
        HandlingTimes(tick(1), tick(1)),
        "synthetic hand-graph fixture",
    )
    return profile, graph


def test_receipt_pays_service_staging_putaway_and_home_return() -> None:
    profile, graph = fixture()
    result = ManualEngine(profile, graph, check_invariants=True).run(tick(25), tick(40))
    # Empty approach2 + intake10 + loaded3 + place1 + pickup1 + loaded5 + place1 =23.
    # The actor then walks S->H10 seconds. All local handling is explicit.
    assert result.at_horizon.stock_units == (("SKU1", 24),)
    assert result.at_horizon.status == "partial"
    assert result.at_end.tick == tick(33)
    assert result.at_end.status == "complete"
    assert result.at_end.workers[0].node_id == "H"
    releases = {(e.resource_ids[0], e.tick) for e in result.events if e.kind == "lease_released"}
    assert ("port:port", tick(12)) in releases
    assert ("buffer:buffer", tick(17)) in releases
    assert ("worker:R01", tick(33)) in releases


def test_outbound_finishes_handover_at_horizon_but_returns_after_it() -> None:
    profile, graph = fixture("outbound")
    # Approach10,pick1,loaded5,place1,pick1,loaded3,service10 =>ship31,return2=>33.
    result = ManualEngine(profile, graph, check_invariants=True).run(tick(31), tick(40))
    assert result.at_horizon.shipped_units == (("SKU1", 24),)
    assert result.at_horizon.stock_units == ()
    assert result.at_horizon.status == "partial"
    assert result.at_end.status == "complete"
    assert result.at_end.tick == tick(33)
    ship = [e for e in result.events if e.kind == "hu_shipped"]
    assert [e.tick for e in ship] == [tick(31)]


def test_unfinished_motion_at_end_is_never_reported_as_completed() -> None:
    profile, graph = fixture()
    result = ManualEngine(profile, graph, check_invariants=True).run(tick(15), tick(18))
    assert result.at_end.tick == tick(18)
    assert result.at_end.status == "partial"
    assert result.at_end.wip_units == (("SKU1", 24),)
    worker = next(w for w in result.at_end.workers if w.actor_id == "R01")
    assert worker.node_id is None
    assert worker.motion is not None and worker.motion.end_tick == tick(22)
    assert all(e.tick <= tick(18) for e in result.events)


def test_closed_intake_keeps_hu_outside_without_inventory_credit() -> None:
    profile, graph = fixture()
    result = ManualEngine(profile, graph, check_invariants=True).run(tick(11), tick(40))
    assert result.at_end.status == "partial"
    assert result.at_end.outside_units == (("SKU1", 24),)
    assert result.at_end.stock_units == result.at_end.wip_units == ()
    assert result.at_end.jobs[0].wait_reason == "port_window"
    assert result.at_end.leases == ()


@pytest.mark.parametrize("archetype,mass", [("IBC", F(1)), ("SMALL_CARTON", F(16))])
def test_unsupported_manual_loads_fail_explicitly(archetype: str, mass: F) -> None:
    profile, graph = fixture()
    changed = replace(profile.handling_units[0], archetype=archetype, gross_mass_kg=mass)
    with pytest.raises(ValueError, match="manual"):
        ManualEngine(replace(profile, handling_units=(changed,)), graph, check_invariants=True)


def test_source_binding_mismatch_fails_before_scheduling() -> None:
    profile, graph = fixture()
    with pytest.raises(ValueError, match="binding"):
        ManualEngine(profile, replace(graph, layout_version="other"), check_invariants=True)
