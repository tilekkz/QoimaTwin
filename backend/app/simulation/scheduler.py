"""Phase-ordered event scheduling on top of SimPy (ADR 0001, ADR 0003).

SimPy owns the clock and the future-event heap. Items scheduled for the same tick and phase are
grouped in one bucket; SimPy fires one bucket event per `(tick, phase)` with `priority=phase`,
so phases at one tick always run in order 0..4. Inside a bucket, items run sorted by `(rank,
key, seq)`. The default rank is zero; age expiry explicitly follows completed scans.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass, field
from enum import IntEnum
from heapq import heappop, heappush

import simpy
from simpy.core import EmptySchedule
from simpy.events import EventPriority

Handler = Callable[[], None]
SettledHook = Callable[[int, int | None], None]
"""(settled_tick, next_tick or None) - called once after all phases of a tick ran."""
SortKey = tuple[str | int, ...]


class Phase(IntEnum):
    COMPLETION = 0
    ARRIVAL = 1
    CONVEYOR = 2
    DISPATCH = 3
    CHECKPOINT = 4


class SchedulingError(RuntimeError):
    """An item was scheduled into the past or into a phase that already ran at this tick."""


@dataclass(slots=True, eq=False)
class ScheduledItem:
    tick: int
    phase: Phase
    key: SortKey
    seq: int
    handler: Handler
    label: str
    unique: Hashable | None
    cancelled: bool = False
    rank: int = 0
    on_cancel: Handler | None = field(default=None, repr=False)

    def cancel(self) -> None:
        if self.cancelled:
            return
        self.cancelled = True
        if self.on_cancel is not None:
            self.on_cancel()


@dataclass(slots=True)
class _Bucket:
    items: list[ScheduledItem] = field(default_factory=list)
    unique: dict[Hashable, ScheduledItem] = field(default_factory=dict)
    live: int = 0

    def cancel_one(self) -> None:
        self.live -= 1


class _BucketEvent(simpy.Event):
    """A pre-triggered SimPy event placed on the heap with the phase as its priority."""

    def __init__(self, env: simpy.Environment, phase: Phase, delay: int) -> None:
        super().__init__(env)
        self._ok = True
        self._value = None
        env.schedule(self, priority=EventPriority(int(phase)), delay=delay)


class PhaseScheduler:
    def __init__(self) -> None:
        self._env = simpy.Environment(initial_time=0)
        self._buckets: dict[tuple[int, Phase], _Bucket] = {}
        self._slots: list[tuple[int, Phase]] = []
        self._seq = 0
        self._running: tuple[int, Phase] | None = None
        self._active_tick: int | None = None
        self.on_tick_settled: SettledHook | None = None

    @property
    def now(self) -> int:
        return int(self._env.now)

    @property
    def running_phase(self) -> Phase | None:
        return self._running[1] if self._running else None

    def schedule(
        self,
        tick: int,
        phase: Phase,
        handler: Handler,
        *,
        key: SortKey = (),
        label: str = "",
        unique: Hashable | None = None,
        rank: int = 0,
    ) -> ScheduledItem:
        self._check_allowed(tick, phase)
        slot = (tick, phase)
        bucket = self._buckets.get(slot)
        if bucket is None:
            bucket = _Bucket()
            self._buckets[slot] = bucket
            _BucketEvent(self._env, phase, tick - self.now).callbacks.append(
                lambda _event: self._fire(slot)
            )
        previous = bucket.unique.get(unique) if unique is not None else None
        if previous is not None and not previous.cancelled:
            return previous
        item = ScheduledItem(
            tick,
            phase,
            key,
            self._seq,
            handler,
            label,
            unique,
            rank=rank,
            on_cancel=bucket.cancel_one,
        )
        if bucket.live == 0:
            heappush(self._slots, slot)
        bucket.live += 1
        self._seq += 1
        bucket.items.append(item)
        if unique is not None:
            bucket.unique[unique] = item
        return item

    def run(self, until: int | None = None) -> None:
        """Process events; with `until`, stop before any event at tick >= until."""
        while True:
            next_tick = self.peek_next_tick()
            if self._active_tick is not None and next_tick != self._active_tick:
                self._settle(next_tick)
            if next_tick is None or (until is not None and next_tick >= until):
                return
            # Empty buckets retain SimPy events after cancellation. Remove those only when
            # advancing to real work; they do not settle ticks or extend the observed clock.
            while self._env.peek() < next_tick:
                self._env.step()
            self._active_tick = next_tick
            try:
                self._env.step()
            except EmptySchedule:  # pragma: no cover - guarded by peek
                return

    def _settle(self, next_tick: int | None) -> None:
        settled, self._active_tick = self._active_tick, None
        if settled is not None and self.on_tick_settled is not None:
            self.on_tick_settled(settled, next_tick)

    def pending_count(self) -> int:
        return sum(bucket.live for bucket in self._buckets.values())

    def peek_next_tick(self) -> int | None:
        while self._slots:
            slot = self._slots[0]
            bucket = self._buckets.get(slot)
            if bucket is not None and bucket.live:
                return slot[0]
            heappop(self._slots)
        return None

    def _check_allowed(self, tick: int, phase: Phase) -> None:
        if tick < self.now:
            raise SchedulingError(f"tick {tick} is in the past (now {self.now})")
        if self._running is not None and tick == self.now and phase <= self._running[1]:
            raise SchedulingError(
                f"phase {phase.name} at tick {tick} cannot be scheduled from phase "
                f"{self._running[1].name}"
            )

    def _fire(self, slot: tuple[int, Phase]) -> None:
        bucket = self._buckets.pop(slot)
        self._running = slot
        try:
            for item in sorted(bucket.items, key=lambda i: (i.rank, i.key, i.seq)):
                if not item.cancelled:
                    item.handler()
        finally:
            self._running = None
