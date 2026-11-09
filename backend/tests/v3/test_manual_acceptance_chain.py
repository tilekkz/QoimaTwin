"""One whole HU can be received and shipped without duplication or early handover."""

from dataclasses import replace

from app.v3.execution import ManualEngine
from app.v3.execution_types import TimedJob
from tests.v3.test_manual_acceptance_fixtures import ManualFixture, fixture, ticks


def chain_fixture() -> ManualFixture:
    data = fixture((1,))
    actors = tuple(
        replace(actor, skills=frozenset({"receive", "ship"}))
        if actor.actor_id in ("R01", "R02")
        else actor
        for actor in data.profile.actors
    )
    ports = tuple(
        replace(port, direction="outbound") if port.port_id == "port2" else port
        for port in data.profile.ports
    )
    jobs = (*data.profile.jobs, TimedJob("J2", 0, "outbound", "HU1", "port2", "slot1"))
    return replace(data, profile=replace(data.profile, actors=actors, ports=ports, jobs=jobs))


def test_single_hu_is_received_then_shipped_once_and_both_actors_return() -> None:
    data = chain_fixture()
    result = ManualEngine(data.profile, data.graph, check_invariants=True).run(ticks(26), ticks(35))
    assert result.at_horizon.shipped_units == (("SKU", 24),)
    assert result.at_horizon.stock_units == result.at_horizon.wip_units == ()
    assert result.at_horizon.outside_units == ()
    assert result.at_horizon.status == "partial"
    assert result.at_end.tick == ticks(28)
    assert result.at_end.status == "complete"
    assert result.at_end.shipped_units == (("SKU", 24),)
    assert len(result.at_end.owners) == 1
    assert all(worker.node_id == "H" for worker in result.at_end.workers)
    shipped = [event for event in result.events if event.kind == "hu_shipped"]
    assert [(event.hu_id, event.tick) for event in shipped] == [("HU1", ticks(26))]


def test_insufficient_outbound_window_keeps_completed_receipt_in_stock() -> None:
    data = chain_fixture()
    result = ManualEngine(data.profile, data.graph, check_invariants=True).run(ticks(15), ticks(35))
    for snapshot in (result.at_horizon, result.at_end):
        assert snapshot.stock_units == (("SKU", 24),)
        assert snapshot.wip_units == snapshot.outside_units == snapshot.shipped_units == ()
        assert snapshot.status == "partial"
        assert len(snapshot.owners) == 1
    assert not [event for event in result.events if event.kind == "hu_shipped"]
