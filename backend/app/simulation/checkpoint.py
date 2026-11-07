"""Replay snapshots every `snapshot_interval_s` on the settled-tick hook (ADR 0003, ADR 0010).

A snapshot at boundary T holds the mutable state after every phase of every tick <= T, so it
covers exactly the events with `seq <= last_seq`. Boundaries that fall between two settled ticks
reuse the state of the earlier one, because nothing changes in between. Boundaries before the
first event hold the initial state. The checkpointer only listens; it never schedules work, so it
cannot keep a drained run alive or move its end tick.

Snapshots are replay snapshots, not engine restart points: see ADR 0010.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.storage.canonical_json import canonical_bytes, parse_json

StateFn = Callable[[int], dict[str, Any]]
"""at_tick -> JSON-compatible mutable state at that boundary."""
LastSeqFn = Callable[[], int]
"""Seq of the last emitted event, or -1 when none."""


@dataclass(frozen=True, slots=True)
class Snapshot:
    """Immutable by construction: the state lives only as canonical JSON bytes."""

    at_tick: int
    last_seq: int
    state_hash: str
    state_bytes: bytes

    @property
    def state(self) -> dict[str, Any]:
        """A fresh decoded copy on every access; changing it never changes the snapshot."""
        decoded: dict[str, Any] = parse_json(self.state_bytes)
        return decoded


class Checkpointer:
    def __init__(self, interval_ticks: int, capture: StateFn, last_seq: LastSeqFn) -> None:
        if interval_ticks <= 0:
            raise ValueError(f"snapshot interval must be positive, got {interval_ticks}")
        self._interval = interval_ticks
        self._capture = capture
        self._last_seq = last_seq
        self._next_boundary = 0
        self._limit: int | None = None
        self._snapshots: list[Snapshot] = []

    @property
    def snapshots(self) -> tuple[Snapshot, ...]:
        return tuple(self._snapshots)

    def begin(self, first_tick: int | None, limit_tick: int) -> None:
        """Arm before the run; emit boundaries that lie before the first scheduled tick.

        `limit_tick` is the last tick the run may reach (the max-drain deadline).
        """
        self._limit = limit_tick
        self._emit_before(first_tick if first_tick is not None else 1)

    def on_tick_settled(self, settled_tick: int, next_tick: int | None) -> None:
        """Settled-tick hook: boundaries in `[settled, next)` see the state after `settled`."""
        if self._limit is None:
            raise RuntimeError("checkpointer.begin() must run before the first settled tick")
        self._emit_before(next_tick if next_tick is not None else settled_tick + 1)

    def _emit_before(self, upper_exclusive: int) -> None:
        if self._limit is None:
            raise RuntimeError("checkpointer.begin() must run before capturing boundaries")
        while self._next_boundary < upper_exclusive and self._next_boundary <= self._limit:
            self._snapshots.append(self._take(self._next_boundary))
            self._next_boundary += self._interval

    def _take(self, at_tick: int) -> Snapshot:
        data = canonical_bytes(self._capture(at_tick))
        return Snapshot(
            at_tick=at_tick,
            last_seq=self._last_seq(),
            state_hash=hashlib.sha256(data).hexdigest(),
            state_bytes=data,
        )
