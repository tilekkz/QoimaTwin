"""A feasibility check must allow a freed slot to receive another HU later."""

from dataclasses import replace

from app.v3.execution import ManualEngine
from app.v3.execution_types import TimedJob
from tests.v3.test_execution_manual import fixture, tick


def test_sequential_receipts_reuse_slot_after_paid_outbound() -> None:
    profile, graph = fixture()
    actors = tuple(
        replace(a, skills=frozenset({"receive", "ship"})) if a.actor_id == "R01" else a
        for a in profile.actors
    )
    port = profile.ports[0]
    outbound = replace(
        port,
        port_id="out",
        direction="outbound",
        buffer_places=(replace(port.buffer_places[0], place_id="out_buffer"),),
    )
    second = replace(profile.handling_units[0], hu_id="HU2")
    jobs = (
        profile.jobs[0],
        TimedJob("ship1", tick(60), "outbound", "HU1", "out", "slot"),
        TimedJob("receive2", tick(120), "inbound", "HU2", "port", "slot"),
    )
    profile = replace(
        profile,
        actors=actors,
        ports=(port, outbound),
        jobs=jobs,
        handling_units=(*profile.handling_units, second),
    )
    result = ManualEngine(profile, graph, check_invariants=True).run(tick(300), tick(400))
    assert result.at_end.status == "complete"
    assert result.at_end.stock_units == result.at_end.shipped_units == (("SKU1", 24),)
