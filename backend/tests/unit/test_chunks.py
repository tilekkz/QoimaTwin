"""60-second event chunks `[k*60, (k+1)*60)` (ADR 0007, ADR 0010).

Chunk lengths are given in ticks; expected values are hand-computed from the half-open rule.
"""

from __future__ import annotations

import pytest

from app.simulation.chunks import chunk_index, split_events
from app.simulation.recorder import Event
from app.simulation.scheduler import Phase

CHUNK = 60


def _event(seq: int, tick: int) -> Event:
    return Event(seq, tick, Phase.COMPLETION, "probe", f"E{seq}", {})


def test_chunk_index_is_half_open() -> None:
    assert chunk_index(0, CHUNK) == 0
    assert chunk_index(59, CHUNK) == 0
    assert chunk_index(60, CHUNK) == 1
    assert chunk_index(119, CHUNK) == 1
    assert chunk_index(120, CHUNK) == 2


def test_event_exactly_on_boundary_belongs_to_next_chunk() -> None:
    events = [_event(0, 0), _event(1, 59), _event(2, 60), _event(3, 60), _event(4, 61)]
    chunks = split_events(events, CHUNK, end_tick=61)
    assert [c.index for c in chunks] == [0, 1]
    assert [(c.start_tick, c.end_tick) for c in chunks] == [(0, 60), (60, 120)]
    assert [[e.seq for e in c.events] for c in chunks] == [[0, 1], [2, 3, 4]]
    assert [(c.first_seq, c.last_seq) for c in chunks] == [(0, 1), (2, 4)]


def test_chunks_cover_run_contiguously_including_empty_ones() -> None:
    events = [_event(0, 10), _event(1, 130)]
    chunks = split_events(events, CHUNK, end_tick=200)
    # end 200 lies in [180, 240): chunks 0..3 inclusive.
    assert [c.index for c in chunks] == [0, 1, 2, 3]
    assert chunks[1].events == ()
    assert (chunks[1].first_seq, chunks[1].last_seq) == (None, None)
    assert [e.seq for c in chunks for e in c.events] == [0, 1]


def test_terminal_event_on_boundary_gets_an_owning_chunk() -> None:
    chunks = split_events([_event(0, 0), _event(1, 120)], CHUNK, end_tick=120)
    assert [c.index for c in chunks] == [0, 1, 2]
    assert [e.seq for e in chunks[2].events] == [1]


def test_run_without_events_has_one_empty_chunk() -> None:
    chunks = split_events([], CHUNK, end_tick=0)
    assert len(chunks) == 1
    assert chunks[0].events == ()


def test_every_event_lands_in_exactly_one_chunk() -> None:
    events = [_event(i, tick) for i, tick in enumerate([0, 0, 59, 60, 60, 119, 120, 179, 180])]
    chunks = split_events(events, CHUNK, end_tick=180)
    flattened = [e.seq for c in chunks for e in c.events]
    assert flattened == list(range(len(events)))
    for chunk in chunks:
        assert all(chunk.start_tick <= e.at_tick < chunk.end_tick for e in chunk.events)


@pytest.mark.parametrize(
    ("events", "chunk_ticks", "end_tick"),
    [
        ([_event(0, 0)], 0, 0),
        ([_event(0, 61)], CHUNK, 60),
        ([_event(0, 5), _event(1, 4)], CHUNK, 10),
        ([_event(0, 1), _event(2, 2)], CHUNK, 10),
        ([], CHUNK, -1),
    ],
    ids=["zero-length", "event-after-end", "time-goes-back", "seq-gap", "negative-end"],
)
def test_invalid_input_is_rejected(events: list[Event], chunk_ticks: int, end_tick: int) -> None:
    with pytest.raises(ValueError):
        split_events(events, chunk_ticks, end_tick)
