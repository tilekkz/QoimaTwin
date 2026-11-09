"""Snapshot boundaries on the settled-tick hook (ADR 0003 phase 4, ADR 0010).

A snapshot at boundary T holds the state after every phase of every tick <= T. The checkpointer
never schedules work, so it cannot keep a run alive. Ticks here are plain integers (interval 30).
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from app.simulation.checkpoint import Checkpointer, Snapshot
from app.simulation.scheduler import Phase, PhaseScheduler
from app.storage.canonical_json import sha256_hex

INTERVAL = 30


class Probe:
    """Scheduler plus a log of handled items; the log is the captured 'state'."""

    def __init__(self, limit: int = 10_000) -> None:
        self.sched = PhaseScheduler()
        self.log: list[str] = []
        self.checkpoints = Checkpointer(INTERVAL, self.capture, self.last_seq)
        self.sched.on_tick_settled = self.checkpoints.on_tick_settled
        self.limit = limit

    def capture(self, at_tick: int) -> dict[str, Any]:
        return {"log": list(self.log), "captured_for": at_tick}

    def last_seq(self) -> int:
        return len(self.log) - 1

    def add(self, tick: int, phase: Phase = Phase.COMPLETION) -> None:
        label = f"{tick}/{int(phase)}"
        self.sched.schedule(tick, phase, lambda: self.log.append(label))

    def run(self, until: int | None = None) -> tuple[Snapshot, ...]:
        self.checkpoints.begin(self.sched.peek_next_tick(), self.limit)
        self.sched.run(until=until)
        return self.checkpoints.snapshots


def _at(snapshots: tuple[Snapshot, ...]) -> list[int]:
    return [s.at_tick for s in snapshots]


def test_snapshot_at_boundary_includes_all_phases_of_that_tick() -> None:
    probe = Probe()
    probe.add(30, Phase.COMPLETION)
    probe.add(30, Phase.DISPATCH)
    probe.add(31, Phase.COMPLETION)
    snapshots = probe.run()
    assert _at(snapshots) == [0, 30]
    assert snapshots[1].state["log"] == ["30/0", "30/3"]
    assert snapshots[1].last_seq == 1


def test_boundaries_before_first_event_hold_initial_state() -> None:
    probe = Probe()
    probe.add(65)
    probe.add(95)
    snapshots = probe.run()
    assert _at(snapshots) == [0, 30, 60, 90]
    assert [s.state["log"] for s in snapshots] == [[], [], [], ["65/0"]]
    assert [s.last_seq for s in snapshots] == [-1, -1, -1, 0]


def test_boundaries_between_events_reuse_settled_state() -> None:
    probe = Probe()
    probe.add(0)
    probe.add(100)
    snapshots = probe.run()
    # Ticks 30, 60 and 90 have no events: state is the one after tick 0.
    assert _at(snapshots) == [0, 30, 60, 90]
    assert [s.state["log"] for s in snapshots] == [["0/0"]] * 4
    assert [s.state["captured_for"] for s in snapshots] == [0, 30, 60, 90]


def test_no_snapshot_after_the_last_settled_tick() -> None:
    probe = Probe()
    probe.add(0)
    probe.add(90)
    snapshots = probe.run()
    assert _at(snapshots) == [0, 30, 60, 90]
    assert snapshots[-1].state["log"] == ["0/0", "90/0"]
    assert probe.sched.now == 90


def test_empty_run_has_one_initial_snapshot() -> None:
    probe = Probe()
    snapshots = probe.run()
    assert _at(snapshots) == [0]
    assert snapshots[0].last_seq == -1


def test_limit_caps_boundaries_when_run_stops_early() -> None:
    probe = Probe(limit=60)
    probe.add(10)
    probe.add(500)
    snapshots = probe.run(until=61)
    assert _at(snapshots) == [0, 30, 60]
    assert probe.sched.pending_count() == 1


def test_checkpointer_schedules_nothing() -> None:
    probe = Probe()
    probe.add(5)
    probe.run()
    assert probe.sched.pending_count() == 0
    assert probe.sched.peek_next_tick() is None
    assert probe.sched.now == 5


def test_hook_requires_begin() -> None:
    checkpoints = Checkpointer(INTERVAL, lambda _t: {}, lambda: -1)
    with pytest.raises(RuntimeError):
        checkpoints.on_tick_settled(0, None)


def test_interval_must_be_positive() -> None:
    with pytest.raises(ValueError):
        Checkpointer(0, lambda _t: {}, lambda: -1)


def test_snapshot_is_frozen_and_isolated() -> None:
    probe = Probe()
    probe.add(0)
    snapshot = probe.run()[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        snapshot.at_tick = 99  # type: ignore[misc]
    state = snapshot.state
    state["log"].append("tampered")
    probe.log.append("engine moved on")
    assert snapshot.state["log"] == ["0/0"]
    assert snapshot.state_hash == sha256_hex(snapshot.state)


def test_snapshot_collection_is_a_copy() -> None:
    probe = Probe()
    probe.add(0)
    first = probe.run()
    assert isinstance(first, tuple)
    assert probe.checkpoints.snapshots == first
