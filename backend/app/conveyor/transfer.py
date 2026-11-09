"""One atomic conveyor tick (ADR 0004).

The plan is computed from the immutable pre-tick occupancy. A cargo moves when its next cell is
empty or is being vacated in the same tick, and when it wins the merge at that cell. Exits leave
the belt when the receiving buffer accepts. Every cargo moves at most one cell. A fully occupied
cycle does not rotate (the tote pool is kept below the loop size, so this never happens in valid
runs).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

EXIT = "__exit__"

RouteFn = Callable[[str, str], str]
"""(cargo_id, cell) -> next cell id, or EXIT when the cargo leaves the belt at this cell."""

ExitOpenFn = Callable[[str, str], bool]
"""(cargo_id, cell) -> True if the buffer after this exit cell accepts the cargo now."""


@dataclass(frozen=True, slots=True)
class Belt:
    successors: Mapping[str, tuple[str, ...]]
    predecessors: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class Move:
    cargo: str
    source: str
    target: str


@dataclass(frozen=True, slots=True)
class Exit:
    cargo: str
    source: str


@dataclass(frozen=True, slots=True)
class TickResult:
    moves: list[Move]
    exits: list[Exit]
    occupancy: dict[str, str]
    cursors: dict[str, int]


class _Planner:
    def __init__(
        self,
        belt: Belt,
        occupancy: Mapping[str, str],
        route: RouteFn,
        exit_open: ExitOpenFn,
        cursors: Mapping[str, int],
    ) -> None:
        self.belt = belt
        self.occupancy = occupancy
        self.route = route
        self.exit_open = exit_open
        self.cursors = dict(cursors)
        self.desired = {cell: route(cargo, cell) for cell, cargo in occupancy.items()}
        self.decided: dict[str, bool] = {}
        self.visiting: set[str] = set()
        self.winner: dict[str, str | None] = {}

    def can_move(self, cell: str) -> bool:
        if cell in self.decided:
            return self.decided[cell]
        if cell in self.visiting:
            return False  # dependency cycle: a full ring never rotates
        self.visiting.add(cell)
        target = self.desired[cell]
        if target == EXIT:
            result = self.exit_open(self.occupancy[cell], cell)
        else:
            free = target not in self.occupancy or self.can_move(target)
            result = free and self._merge_winner(target) == cell
        self.visiting.discard(cell)
        self.decided[cell] = result
        return result

    def _merge_winner(self, target: str) -> str | None:
        if target in self.winner:
            return self.winner[target]
        sources = self.belt.predecessors[target]
        contenders = [s for s in sources if self.desired.get(s) == target]
        chosen: str | None = None
        if len(contenders) == 1:
            chosen = contenders[0]
        elif contenders:
            start = self.cursors.get(target, 0) % len(sources)
            for offset in range(len(sources)):
                candidate = sources[(start + offset) % len(sources)]
                if candidate in contenders:
                    chosen = candidate
                    break
        self.winner[target] = chosen
        return chosen

    def commit(self) -> TickResult:
        ordered = sorted(self.occupancy)
        movers = [cell for cell in ordered if self.can_move(cell)]
        moves = [
            Move(self.occupancy[c], c, self.desired[c]) for c in movers if self.desired[c] != EXIT
        ]
        exits = [Exit(self.occupancy[c], c) for c in movers if self.desired[c] == EXIT]
        vacated = set(movers)
        occupancy = {c: cargo for c, cargo in self.occupancy.items() if c not in vacated}
        for move in moves:
            occupancy[move.target] = move.cargo
            sources = self.belt.predecessors[move.target]
            if len(sources) > 1:
                self.cursors[move.target] = (sources.index(move.source) + 1) % len(sources)
        return TickResult(moves=moves, exits=exits, occupancy=occupancy, cursors=self.cursors)


def plan_tick(
    belt: Belt,
    occupancy: Mapping[str, str],
    route: RouteFn,
    exit_open: ExitOpenFn,
    cursors: Mapping[str, int],
) -> TickResult:
    """Plan and commit one tick. Inputs are not mutated; the result carries the new state."""
    return _Planner(belt, occupancy, route, exit_open, cursors).commit()
