"""PhaseScheduler on SimPy: ordering by (tick, phase, key, seq) (ADR 0001, 0003)."""

from __future__ import annotations

import pytest

from app.simulation.scheduler import Phase, PhaseScheduler, SchedulingError


def test_items_run_in_tick_then_phase_order() -> None:
    sched = PhaseScheduler()
    log: list[str] = []
    sched.schedule(10, Phase.DISPATCH, lambda: log.append("10/3"))
    sched.schedule(10, Phase.COMPLETION, lambda: log.append("10/0"))
    sched.schedule(5, Phase.CHECKPOINT, lambda: log.append("5/4"))
    sched.schedule(10, Phase.CONVEYOR, lambda: log.append("10/2"))
    sched.schedule(10, Phase.ARRIVAL, lambda: log.append("10/1"))
    sched.run()
    assert log == ["5/4", "10/0", "10/1", "10/2", "10/3"]


def test_same_phase_items_run_by_key_then_insertion() -> None:
    sched = PhaseScheduler()
    log: list[str] = []
    sched.schedule(7, Phase.COMPLETION, lambda: log.append("P02"), key=("P02",))
    sched.schedule(7, Phase.COMPLETION, lambda: log.append("P01-b"), key=("P01",))
    sched.schedule(7, Phase.COMPLETION, lambda: log.append("P01-c"), key=("P01",))
    sched.schedule(7, Phase.COMPLETION, lambda: log.append("K01"), key=("K01",))
    sched.run()
    assert log == ["K01", "P01-b", "P01-c", "P02"]


def test_handler_can_schedule_later_phase_same_tick() -> None:
    sched = PhaseScheduler()
    log: list[str] = []

    def completion() -> None:
        log.append("done")
        sched.schedule(sched.now, Phase.DISPATCH, lambda: log.append("dispatch"))

    sched.schedule(3, Phase.COMPLETION, completion)
    sched.run()
    assert log == ["done", "dispatch"]
    assert sched.now == 3


def test_handler_cannot_schedule_into_running_or_past_phase() -> None:
    sched = PhaseScheduler()
    errors: list[str] = []

    def dispatch() -> None:
        for phase in (Phase.COMPLETION, Phase.DISPATCH):
            try:
                sched.schedule(sched.now, phase, lambda: None)
            except SchedulingError as exc:
                errors.append(str(exc))

    sched.schedule(4, Phase.DISPATCH, dispatch)
    sched.run()
    assert len(errors) == 2


def test_scheduling_in_the_past_is_rejected() -> None:
    sched = PhaseScheduler()
    sched.schedule(10, Phase.COMPLETION, lambda: None)
    sched.run()
    with pytest.raises(SchedulingError):
        sched.schedule(9, Phase.CHECKPOINT, lambda: None)


def test_unique_key_coalesces_duplicate_requests() -> None:
    sched = PhaseScheduler()
    calls: list[int] = []
    first = sched.schedule(6, Phase.DISPATCH, lambda: calls.append(1), unique="cycle")
    second = sched.schedule(6, Phase.DISPATCH, lambda: calls.append(2), unique="cycle")
    sched.run()
    assert first is second
    assert calls == [1]


def test_cancelled_item_does_not_run() -> None:
    sched = PhaseScheduler()
    calls: list[str] = []
    handle = sched.schedule(2, Phase.COMPLETION, lambda: calls.append("x"))
    sched.schedule(2, Phase.ARRIVAL, lambda: calls.append("y"))
    handle.cancel()
    sched.run()
    assert calls == ["y"]


def test_run_until_stops_before_limit_and_keeps_pending() -> None:
    sched = PhaseScheduler()
    calls: list[int] = []
    sched.schedule(5, Phase.COMPLETION, lambda: calls.append(5))
    sched.schedule(15, Phase.COMPLETION, lambda: calls.append(15))
    sched.run(until=10)
    assert calls == [5]
    assert sched.pending_count() == 1
    sched.run()
    assert calls == [5, 15]


def test_peek_next_tick_reports_earliest_live_item() -> None:
    sched = PhaseScheduler()
    assert sched.peek_next_tick() is None
    handle = sched.schedule(8, Phase.ARRIVAL, lambda: None)
    sched.schedule(12, Phase.ARRIVAL, lambda: None)
    assert sched.peek_next_tick() == 8
    handle.cancel()
    assert sched.peek_next_tick() == 12


def test_handler_exception_propagates() -> None:
    sched = PhaseScheduler()

    def boom() -> None:
        raise RuntimeError("handler failed")

    sched.schedule(1, Phase.COMPLETION, boom)
    with pytest.raises(RuntimeError, match="handler failed"):
        sched.run()
