"""Directed cell graph compiled from conveyor segments and ports.

Cell IDs are `segment_id:index`. A port at exact offset `o` on a source segment and `p` on the
target links source cell `o/cell - 1` to target cell `p/cell` (see contracts/README.md).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import StrEnum

from app.contracts.base import exact
from app.contracts.layout import Layout
from app.contracts.validation import port_offset


class TopologyError(Exception):
    """The conveyor description cannot be compiled into a consistent cell graph."""


class ExitKind(StrEnum):
    PACK_BUFFER = "pack_buffer"
    SHIPPING_BUFFER = "shipping_buffer"


@dataclass(frozen=True, slots=True)
class CellExit:
    kind: ExitKind
    target_id: str


def cell_id(segment_id: str, index: int) -> str:
    return f"{segment_id}:{index}"


def cell_sort_key(cell: str) -> tuple[str, int]:
    segment, index = cell.rsplit(":", 1)
    return (segment, int(index))


@dataclass(frozen=True, slots=True)
class ConveyorTopology:
    cells: tuple[str, ...]
    successors: dict[str, tuple[str, ...]]
    predecessors: dict[str, tuple[str, ...]]
    exits: dict[str, CellExit]
    induction_inlets: dict[str, str]
    pack_outlets: dict[str, str]
    _next_hop: dict[str, dict[str, str]]

    @classmethod
    def from_layout(cls, layout: Layout) -> ConveyorTopology:
        conveyor = layout.conveyor
        cell_length = exact(conveyor.cell_length_m)
        segments = {s.segment_id: s for s in conveyor.segments}
        succ: dict[str, set[str]] = {}
        for seg in conveyor.segments:
            for i in range(seg.cell_count):
                succ[cell_id(seg.segment_id, i)] = set()
                if i + 1 < seg.cell_count:
                    succ[cell_id(seg.segment_id, i)].add(cell_id(seg.segment_id, i + 1))
        for link in conveyor.connections:
            src_seg, dst_seg = segments[link.from_segment_id], segments[link.to_segment_id]
            src_off, dst_off = port_offset(src_seg, link.at), port_offset(dst_seg, link.at)
            if src_off is None or dst_off is None:
                raise TopologyError(
                    f"port {link.from_segment_id}->{link.to_segment_id} is off-segment"
                )
            src = cell_id(src_seg.segment_id, int(src_off / cell_length) - 1)
            dst = cell_id(dst_seg.segment_id, int(dst_off / cell_length))
            if src not in succ or dst not in succ:
                raise TopologyError(
                    f"port {link.from_segment_id}->{link.to_segment_id} has no cell"
                )
            succ[src].add(dst)

        exits: dict[str, CellExit] = {}
        for station in layout.pack_stations:
            last = segments[station.input_segment_id].cell_count - 1
            exits[cell_id(station.input_segment_id, last)] = CellExit(
                ExitKind.PACK_BUFFER, station.pack_id
            )
        terminal = segments[conveyor.terminal.segment_id]
        exits[cell_id(terminal.segment_id, terminal.cell_count - 1)] = CellExit(
            ExitKind.SHIPPING_BUFFER, "SHIPPING"
        )
        for cell, outgoing in succ.items():
            if not outgoing and cell not in exits:
                raise TopologyError(f"cell {cell} is a dead end")

        successors = {c: tuple(sorted(s, key=cell_sort_key)) for c, s in succ.items()}
        pred: dict[str, list[str]] = {c: [] for c in succ}
        for cell, next_cells in successors.items():
            for nxt in next_cells:
                pred[nxt].append(cell)
        predecessors = {c: tuple(sorted(p, key=cell_sort_key)) for c, p in pred.items()}
        cells = tuple(sorted(succ, key=cell_sort_key))
        return cls(
            cells=cells,
            successors=successors,
            predecessors=predecessors,
            exits=exits,
            induction_inlets={
                i.induction_id: cell_id(i.feed_segment_id, 0) for i in layout.inductions
            },
            pack_outlets={p.pack_id: cell_id(p.output_segment_id, 0) for p in layout.pack_stations},
            _next_hop={
                exit_.target_id: _next_hops_towards(exit_cell, predecessors)
                for exit_cell, exit_ in exits.items()
            },
        )

    def next_cell_towards(self, cell: str, target_id: str) -> str | None:
        """Next cell on the route to the exit of `target_id`; None when `cell` is that exit cell."""
        hops = self._next_hop.get(target_id)
        if hops is None:
            raise TopologyError(f"unknown conveyor target {target_id}")
        if self.exits.get(cell, CellExit(ExitKind.SHIPPING_BUFFER, "")).target_id == target_id:
            return None
        if cell not in hops:
            raise TopologyError(f"{target_id} is not reachable from {cell}")
        return hops[cell]

    def travel_cells(self, start: str, end: str) -> int:
        """Cells traversed from entering `start` until leaving `end` (one second each at 1 m/s)."""
        queue: deque[tuple[str, int]] = deque([(start, 1)])
        seen = {start}
        while queue:
            cell, count = queue.popleft()
            if cell == end:
                return count
            for nxt in self.successors[cell]:
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append((nxt, count + 1))
        raise TopologyError(f"{end} is not reachable from {start}")


def _next_hops_towards(exit_cell: str, predecessors: dict[str, tuple[str, ...]]) -> dict[str, str]:
    """Reverse BFS from an exit: for each cell, the successor on a shortest route to the exit."""
    hops: dict[str, str] = {}
    queue: deque[str] = deque([exit_cell])
    seen = {exit_cell}
    while queue:
        cell = queue.popleft()
        for prev in predecessors[cell]:
            if prev not in seen:
                seen.add(prev)
                hops[prev] = cell
                queue.append(prev)
    return hops
