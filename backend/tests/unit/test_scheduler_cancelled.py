"""Cancelled timers are not useful work and must not extend drain or checkpoints."""

from app.simulation.scheduler import Phase, PhaseScheduler


def test_cancelled_timer_does_not_advance_clock_or_settle_a_fake_tick() -> None:
    scheduler = PhaseScheduler()
    settled: list[tuple[int, int | None]] = []
    scheduler.on_tick_settled = lambda tick, nxt: settled.append((tick, nxt))
    timer = scheduler.schedule(300, Phase.COMPLETION, lambda: None)
    scheduler.schedule(54, Phase.DISPATCH, timer.cancel)
    scheduler.schedule(96, Phase.COMPLETION, lambda: None)
    scheduler.run()
    assert scheduler.now == 96
    assert settled == [(54, 96), (96, None)]
    assert scheduler.pending_count() == 0


def test_cancelled_bucket_before_live_event_is_not_a_settled_timestamp() -> None:
    scheduler = PhaseScheduler()
    settled: list[tuple[int, int | None]] = []
    scheduler.on_tick_settled = lambda tick, nxt: settled.append((tick, nxt))
    scheduler.schedule(50, Phase.COMPLETION, lambda: None).cancel()
    scheduler.schedule(100, Phase.ARRIVAL, lambda: None)
    scheduler.run(until=75)
    assert scheduler.now == 0
    assert settled == []
    scheduler.run()
    assert scheduler.now == 100
    assert settled == [(100, None)]


def test_live_bucket_after_cancelled_bucket_in_same_tick_is_processed() -> None:
    scheduler = PhaseScheduler()
    seen: list[int] = []
    scheduler.schedule(1, Phase.COMPLETION, lambda: seen.append(0)).cancel()
    scheduler.schedule(1, Phase.ARRIVAL, lambda: seen.append(1))
    scheduler.run()
    assert seen == [1]
    assert scheduler.now == 1
