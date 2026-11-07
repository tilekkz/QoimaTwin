"""Hand timeline assertions fixed before ManualEngine implementation."""

from dataclasses import replace

import pytest

from app.v3.execution import ManualEngine
from app.v3.execution_types import ManualEvent
from tests.v3.test_manual_acceptance_fixtures import fixture, ticks


def lease_times(events: tuple[ManualEvent, ...], resource: str, kind: str) -> list[int]:
    return [event.tick for event in events if event.kind == kind and resource in event.resource_ids]


def test_two_actual_workers_are_shared_across_three_ports_and_pay_return() -> None:
    data = fixture()
    assert len(data.profile.actors) == len({actor.actor_id for actor in data.profile.actors}) == 24
    result = ManualEngine(data.profile, data.graph, check_invariants=True).run(ticks(25), ticks(40))
    assert result.at_horizon.stock_units == (("SKU", 72),)
    assert result.at_horizon.status == "partial"
    assert result.at_end.status == "complete"
    assert result.at_end.tick == ticks(30)
    assert lease_times(result.events, "worker:R01", "lease_acquired") == [0, ticks(13)]
    assert lease_times(result.events, "worker:R01", "lease_released") == [ticks(13), ticks(30)]
    assert lease_times(result.events, "worker:R02", "lease_acquired") == [0]
    assert lease_times(result.events, "worker:R02", "lease_released") == [ticks(15)]
    occupied = (13 - 0) + (30 - 13) + (15 - 0)
    assert occupied == 45  # Person-seconds differ from 30 elapsed seconds.
    assert all(worker.node_id == "H" and worker.motion is None for worker in result.at_end.workers)


def test_cutoff_includes_exact_stock_event_but_does_not_dispatch_after_horizon() -> None:
    data = fixture()
    result = ManualEngine(data.profile, data.graph, check_invariants=True).run(ticks(9), ticks(40))
    assert result.at_horizon.stock_units == (("SKU", 24),)
    assert result.at_horizon.wip_units == (("SKU", 24),)
    assert result.at_horizon.outside_units == (("SKU", 24),)
    assert result.at_end.stock_units == (("SKU", 48),)
    assert result.at_end.wip_units == result.at_end.shipped_units == ()
    assert result.at_end.outside_units == (("SKU", 24),)
    assert result.at_end.status == "partial"
    assert lease_times(result.events, "worker:R01", "lease_acquired") == [0]


def test_one_buffer_blocks_otherwise_free_worker_until_pickup_finishes() -> None:
    data = fixture((1, 1))
    result = ManualEngine(data.profile, data.graph, check_invariants=True).run(ticks(20), ticks(25))
    assert result.at_end.tick == ticks(19)
    assert result.at_end.stock_units == (("SKU", 48),)
    assert lease_times(result.events, "buffer:buffer1", "lease_acquired") == [0, ticks(6)]
    assert lease_times(result.events, "buffer:buffer1", "lease_released") == [ticks(6), ticks(12)]
    assert lease_times(result.events, "worker:R02", "lease_acquired") == [ticks(6)]
    assert lease_times(result.events, "worker:R02", "lease_released") == [ticks(19)]


def test_buffered_cargo_is_wip_and_waiting_receipt_stays_outside() -> None:
    data = fixture((1, 1))
    result = ManualEngine(data.profile, data.graph, check_invariants=True).run(ticks(5), ticks(20))
    assert result.at_horizon.stock_units == ()
    assert result.at_horizon.wip_units == (("SKU", 24),)
    assert result.at_horizon.outside_units == (("SKU", 24),)
    assert result.at_end.stock_units == (("SKU", 24),)
    assert result.at_end.outside_units == (("SKU", 24),)


@pytest.mark.parametrize("shorter", [False, True])
def test_port_window_allows_exact_service_finish_but_not_one_tick_excess(shorter: bool) -> None:
    data = fixture((1,))
    port = replace(data.profile.ports[0], windows=((0, ticks(3) - int(shorter)),))
    profile = replace(data.profile, ports=(port, *data.profile.ports[1:]))
    result = ManualEngine(profile, data.graph, check_invariants=True).run(ticks(20), ticks(25))
    assert result.at_end.stock_units == (() if shorter else (("SKU", 24),))
    assert result.at_end.outside_units == ((("SKU", 24),) if shorter else ())
    assert result.at_end.leases == ()
    assert lease_times(result.events, "port:port1", "lease_released") == (
        [] if shorter else [ticks(3)]
    )


@pytest.mark.parametrize("shorter", [False, True])
def test_horizon_allows_exact_service_finish_and_drains_internal_work(shorter: bool) -> None:
    data = fixture((1,))
    result = ManualEngine(data.profile, data.graph, check_invariants=True).run(
        ticks(3) - int(shorter),
        ticks(20),
    )
    assert result.at_end.stock_units == (() if shorter else (("SKU", 24),))
    assert result.at_end.outside_units == ((("SKU", 24),) if shorter else ())
    if not shorter:
        assert result.at_end.tick == ticks(13)
        assert result.at_end.status == "complete"


def test_delayed_arrival_shifts_whole_hand_timeline_without_early_reservation() -> None:
    data = fixture((1,), arrival_s=4)
    result = ManualEngine(data.profile, data.graph, check_invariants=True).run(ticks(20), ticks(25))
    assert result.at_end.tick == ticks(17)
    assert lease_times(result.events, "worker:R01", "lease_acquired") == [ticks(4)]
    assert lease_times(result.events, "port:port1", "lease_released") == [ticks(7)]
    assert all(event.tick >= ticks(4) for event in result.events)


def test_dispatch_wakes_before_future_window_to_pay_approach_and_finish_exactly() -> None:
    data = fixture((1,))
    port = replace(data.profile.ports[0], windows=((ticks(5), ticks(7)),))
    profile = replace(data.profile, ports=(port, *data.profile.ports[1:]))
    result = ManualEngine(profile, data.graph, check_invariants=True).run(ticks(20), ticks(25))
    # Approach[4,5], service[5,7], storage13, paid return17.
    assert lease_times(result.events, "worker:R01", "lease_acquired") == [ticks(4)]
    assert lease_times(result.events, "port:port1", "lease_released") == [ticks(7)]
    assert result.at_end.stock_units == (("SKU", 24),)
    assert result.at_end.tick == ticks(17)
