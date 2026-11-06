"""Atomic conveyor tick on small synthetic graphs (gates C1-C4, C7; ADR 0004)."""

from __future__ import annotations

from app.conveyor.transfer import EXIT, Belt, plan_tick


def _line() -> Belt:
    # C1 -> C2 -> C3 -> exit
    return Belt(
        successors={"C1": ("C2",), "C2": ("C3",), "C3": ()},
        predecessors={"C1": (), "C2": ("C1",), "C3": ("C2",)},
    )


def _always(_cargo: str, cell: str) -> str:
    return {"C1": "C2", "C2": "C3", "C3": EXIT, "S1": "M", "S2": "M", "M": EXIT}[cell]


def test_C1_one_hop_per_tick_until_exit() -> None:
    belt = _line()
    occupancy = {"C1": "A"}
    trace = []
    for _ in range(3):
        result = plan_tick(belt, occupancy, _always, lambda _c, _cell: True, {})
        occupancy = result.occupancy
        trace.append((dict(occupancy), [e.cargo for e in result.exits]))
    assert trace == [({"C2": "A"}, []), ({"C3": "A"}, []), ({}, ["A"])]


def test_C2_occupied_first_cell_blocks_admission_request() -> None:
    belt = _line()
    result = plan_tick(
        belt, {"C1": "A", "C2": "B", "C3": "Z"}, _always, lambda _c, _cell: False, {}
    )
    assert result.occupancy == {"C1": "A", "C2": "B", "C3": "Z"}
    assert result.moves == []


def test_C3_release_propagates_without_double_hop() -> None:
    belt = _line()
    occupancy = {"C3": "A", "C2": "B"}
    blocked = plan_tick(belt, occupancy, _always, lambda _c, _cell: False, {})
    assert blocked.occupancy == occupancy
    opened = plan_tick(belt, occupancy, _always, lambda _c, _cell: True, {})
    assert [e.cargo for e in opened.exits] == ["A"]
    assert opened.occupancy == {"C3": "B"}
    final = plan_tick(belt, opened.occupancy, _always, lambda _c, _cell: True, {})
    assert [e.cargo for e in final.exits] == ["B"]


def test_whole_queue_advances_together_when_head_exits() -> None:
    belt = _line()
    result = plan_tick(belt, {"C1": "C", "C2": "B", "C3": "A"}, _always, lambda *_: True, {})
    assert result.occupancy == {"C2": "C", "C3": "B"}
    assert [e.cargo for e in result.exits] == ["A"]


def _merge() -> Belt:
    # S1 -> M, S2 -> M, M -> exit
    return Belt(
        successors={"S1": ("M",), "S2": ("M",), "M": ()},
        predecessors={"S1": (), "S2": (), "M": ("S1", "S2")},
    )


def test_C4_round_robin_grants_alternate_and_are_repeatable() -> None:
    def run() -> list[str]:
        belt = _merge()
        cursors: dict[str, int] = {"M": 0}
        grants = []
        counter = 0
        occupancy: dict[str, str] = {}
        for _ in range(4):
            for source in ("S1", "S2"):
                if source not in occupancy:
                    counter += 1
                    occupancy[source] = f"{source}#{counter}"
            result = plan_tick(belt, occupancy, _always, lambda *_: True, cursors)
            cursors = result.cursors
            grants += [m.source for m in result.moves if m.target == "M"]
            occupancy = result.occupancy
        return grants

    assert run() == ["S1", "S2", "S1", "S2"]
    assert run() == run()


def test_merge_cursor_does_not_advance_without_grant() -> None:
    belt = _merge()
    result = plan_tick(belt, {"S2": "B", "M": "X"}, _always, lambda *_: False, {"M": 0})
    assert result.cursors == {"M": 0}
    assert result.moves == []


def test_single_contender_wins_even_if_cursor_points_elsewhere() -> None:
    belt = _merge()
    result = plan_tick(belt, {"S2": "B"}, _always, lambda *_: True, {"M": 0})
    assert result.occupancy == {"M": "B"}
    assert result.cursors == {"M": 0}


def test_full_cycle_does_not_rotate() -> None:
    ring = Belt(
        successors={"R1": ("R2",), "R2": ("R1",)},
        predecessors={"R1": ("R2",), "R2": ("R1",)},
    )
    result = plan_tick(
        ring,
        {"R1": "A", "R2": "B"},
        lambda _c, cell: "R2" if cell == "R1" else "R1",
        lambda *_: True,
        {},
    )
    assert result.moves == []


def test_exits_and_moves_are_reported_in_cell_order() -> None:
    belt = _line()
    result = plan_tick(belt, {"C1": "C", "C3": "A"}, _always, lambda *_: True, {})
    assert [(m.cargo, m.source, m.target) for m in result.moves] == [("C", "C1", "C2")]
    assert [(e.cargo, e.source) for e in result.exits] == [("A", "C3")]
