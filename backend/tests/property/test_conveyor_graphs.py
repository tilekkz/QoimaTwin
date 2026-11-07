"""PDF p8 / ADR0004: conservation, one hop, no collisions, and bounded merge fairness."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.conveyor.transfer import EXIT, Belt, Exit, Move, plan_tick

pytestmark = pytest.mark.property


@dataclass
class GraphCase:
    belt: Belt
    occupancy: dict[str, str]
    targets: dict[str, str]
    open_exits: set[str]
    cursors: dict[str, int]


@st.composite
def graph_cases(draw: st.DrawFn) -> GraphCase:
    count = draw(st.integers(1, 9))
    cells = [f"C{i}" for i in range(count)]
    edges = draw(st.sets(st.tuples(st.sampled_from(cells), st.sampled_from(cells))))
    edges = {(a, b) for a, b in edges if a != b}
    successors = {c: tuple(sorted(b for a, b in edges if a == c)) for c in cells}
    predecessors = {c: tuple(sorted(a for a, b in edges if b == c)) for c in cells}
    occupied = draw(st.sets(st.sampled_from(cells)))
    occupancy = {c: f"cargo-{c}" for c in sorted(occupied)}
    targets = {c: draw(st.sampled_from((c, EXIT, *successors[c]))) for c in occupancy}
    opened = draw(st.sets(st.sampled_from(cells)))
    cursors = {c: draw(st.integers(0, count * 3)) for c in cells}
    return GraphCase(Belt(successors, predecessors), occupancy, targets, opened, cursors)


@settings(max_examples=150, deadline=None)
@given(case=graph_cases())
def test_random_graph_tick_is_conservative_atomic_and_order_independent(case: GraphCase) -> None:
    before, cursors = case.occupancy.copy(), case.cursors.copy()
    result = plan_tick(
        case.belt, before, lambda _, c: case.targets[c], lambda _, c: c in case.open_exits, cursors
    )
    changed = [m.cargo for m in result.moves] + [e.cargo for e in result.exits]
    assert len(changed) == len(set(changed))  # one hop or exit per cargo, never both
    assert len(result.occupancy.values()) == len(set(result.occupancy.values()))
    assert set(result.occupancy.values()).isdisjoint(e.cargo for e in result.exits)
    assert set(before.values()) == set(result.occupancy.values()) | {e.cargo for e in result.exits}
    replay = before.copy()
    movements: list[Move | Exit] = [*result.moves, *result.exits]
    for movement in movements:
        assert replay.pop(movement.source) == movement.cargo
    assert all(case.targets[e.source] == EXIT and e.source in case.open_exits for e in result.exits)
    for move in result.moves:
        assert move.target in case.belt.successors[move.source]
        assert move.target not in replay
        replay[move.target] = move.cargo
    assert replay == result.occupancy
    assert before == case.occupancy and cursors == case.cursors
    reversed_input = dict(reversed(list(before.items())))
    assert result == plan_tick(
        case.belt,
        reversed_input,
        lambda _, c: case.targets[c],
        lambda _, c: c in case.open_exits,
        dict(reversed(list(cursors.items()))),
    )


def _grants(count: int, blocked: int, cursor: int, rounds: int) -> list[str]:
    sources = tuple(f"S{i}" for i in range(count))
    belt = Belt(
        {**dict.fromkeys(sources, ("M",)), "M": ()},
        {**dict.fromkeys(sources, ()), "M": sources},
    )
    occupancy = {s: s for s in sources}
    cursors, grants = {"M": cursor}, []
    for _ in range(rounds):
        result = plan_tick(
            belt,
            occupancy,
            lambda _, c: EXIT if c == "M" else c if c == f"S{blocked}" else "M",
            lambda *_: True,
            cursors,
        )
        assert len(result.moves) == 1
        grants.append(result.moves[0].source)
        cursors = result.cursors
        occupancy = {**result.occupancy, result.moves[0].source: f"replacement-{len(grants)}"}
    return grants


@settings(max_examples=50, deadline=None)
@given(count=st.integers(2, 7), blocked=st.integers(0, 20), cursor=st.integers(0, 20))
def test_continuous_merge_contenders_each_win_once_per_cycle(
    count: int, blocked: int, cursor: int
) -> None:
    blocked %= count
    active = {f"S{i}" for i in range(count) if i != blocked}
    grants = _grants(count, blocked, cursor, (count - 1) * 3)
    for offset in range(len(grants) - len(active) + 1):
        assert set(grants[offset : offset + len(active)]) == active


def test_three_way_merge_skips_blocked_source_and_wraps_cursor() -> None:
    # Source order S0,S1,S2; cursor2 grants S2, wraps to S0, and skips blocked S1.
    assert _grants(count=3, blocked=1, cursor=2, rounds=6) == ["S2", "S0"] * 3
