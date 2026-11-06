"""Event chunks over half-open windows `[k*L, (k+1)*L)` (ADR 0007, ADR 0010).

An event exactly on a boundary belongs to the next chunk. Chunks cover the run contiguously from
tick 0 to the chunk that contains the end tick, so a terminal event on a boundary still has an
owning chunk and empty windows are kept. Events must arrive in `seq` order without gaps; every
event lands in exactly one chunk.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

from app.simulation.recorder import Event


@dataclass(frozen=True, slots=True)
class Chunk:
    index: int
    start_tick: int
    end_tick: int
    """Exclusive."""
    first_seq: int | None
    last_seq: int | None
    events: tuple[Event, ...]


def chunk_index(tick: int, chunk_ticks: int) -> int:
    if chunk_ticks <= 0:
        raise ValueError(f"chunk length must be positive, got {chunk_ticks}")
    if tick < 0:
        raise ValueError(f"tick must be non-negative, got {tick}")
    return tick // chunk_ticks


def _check_stream(events: Sequence[Event], end_tick: int) -> None:
    for prev, event in pairwise(events):
        if event.seq != prev.seq + 1:
            raise ValueError(f"event seq {event.seq} does not follow {prev.seq}")
        if event.at_tick < prev.at_tick:
            raise ValueError(f"event {event.seq} at tick {event.at_tick} goes back in time")
    if events and events[-1].at_tick > end_tick:
        raise ValueError(f"event {events[-1].seq} is after the run end tick {end_tick}")


def split_events(events: Sequence[Event], chunk_ticks: int, end_tick: int) -> tuple[Chunk, ...]:
    """Split an ordered event stream into contiguous chunks covering `[0, end_tick]`."""
    last_index = chunk_index(end_tick, chunk_ticks)
    _check_stream(events, end_tick)
    buckets: list[list[Event]] = [[] for _ in range(last_index + 1)]
    for event in events:
        buckets[chunk_index(event.at_tick, chunk_ticks)].append(event)
    return tuple(
        Chunk(
            index=k,
            start_tick=k * chunk_ticks,
            end_tick=(k + 1) * chunk_ticks,
            first_seq=bucket[0].seq if bucket else None,
            last_seq=bucket[-1].seq if bucket else None,
            events=tuple(bucket),
        )
        for k, bucket in enumerate(buckets)
    )
