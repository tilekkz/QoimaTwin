"""Business completion differs from the worker's paid return and resource release."""

from app.v3.execution import ManualEngine
from tests.v3.test_manual_acceptance_fixtures import business_fixture, ticks


def test_outbound_handover_at_31_precedes_worker_return_at_33() -> None:
    data = business_fixture("outbound")
    result = ManualEngine(data.profile, data.graph, check_invariants=True).run(ticks(32), ticks(40))
    # 10 approach +1pick +5carry +1place +1pick +3carry +10service =31.
    # Paid empty return adds2 seconds. Job terminal state is a resource boundary.
    assert result.at_horizon.shipped_units == (("SKU", 24),)
    assert result.at_horizon.stock_units == result.at_horizon.wip_units == ()
    assert result.at_horizon.jobs[0].state == "returning"
    assert result.at_horizon.owners[0].kind == "shipped"
    assert [event.tick for event in result.events if event.kind == "hu_shipped"] == [ticks(31)]
    assert [event.tick for event in result.events if event.kind == "job_completed"] == [ticks(33)]
    worker = next(worker for worker in result.at_horizon.workers if worker.actor_id == "R01")
    assert worker.motion is not None and worker.motion.end_tick == ticks(33)
    assert result.at_end.tick == ticks(33)


def test_receipt_stock_at_23_precedes_worker_return_at_33() -> None:
    data = business_fixture("inbound")
    result = ManualEngine(data.profile, data.graph, check_invariants=True).run(ticks(24), ticks(40))
    # 2approach+10service+3carry+1place+1pick+5carry+1place =23; return10=>33.
    assert result.at_horizon.stock_units == (("SKU", 24),)
    assert result.at_horizon.wip_units == result.at_horizon.outside_units == ()
    assert result.at_horizon.jobs[0].state == "returning"
    assert result.at_horizon.owners[0].kind == "stock"
    placed = [
        event.tick
        for event in result.events
        if event.owner is not None and event.owner.kind == "stock"
    ]
    assert placed == [ticks(23)]
    assert [event.tick for event in result.events if event.kind == "job_completed"] == [ticks(33)]
    assert result.at_end.tick == ticks(33)
