"""Before-shift relocation actions and transfer records for later replay (01 §9).

One relocation worker walks each chosen route from the relocation home and back. Each swap
is A->buffer, B->A, buffer->B with six take/place handlings. Times are offsets from the
relocation window start on a separate pre-shift calendar; the shift start does not move.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Literal

from app.contracts.assignment import InitialLot
from app.planning.errors import PlanningInputError
from app.planning.geometry import PlanningGeometry
from app.planning.models import RelocationAction, RelocationSchedule, TransferRecord
from app.planning.routes import SwapRoute, WorkerRates

RELOCATION_ACTOR_ID = "RELOCATION_01"
Operation = Literal["relocation_take", "relocation_place"]


def to_ticks(seconds: Fraction, tps: int) -> int:
    value = seconds * tps
    if value.denominator != 1:
        raise PlanningInputError(f"{seconds} s is not on the {tps}/s time grid")
    return value.numerator


@dataclass(slots=True)
class _Timeline:
    geo: PlanningGeometry
    tps: int
    walk_ticks_per_metre: Fraction
    handle_ticks: int
    now: int = 0
    actions: list[RelocationAction] = field(default_factory=list)

    def _add(
        self,
        swap: int,
        state: str,
        operation: str,
        end: int,
        nodes: tuple[str, ...],
        lot_id: str | None,
    ) -> tuple[int, int]:
        start, self.now = self.now, end
        self.actions.append(
            RelocationAction.model_validate(
                {
                    "action_id": f"RLA{len(self.actions) + 1:05d}",
                    "actor_id": RELOCATION_ACTOR_ID,
                    "swap_index": swap,
                    "state": state,
                    "operation": operation,
                    "start_tick": start,
                    "end_tick": end,
                    "start_s": float(Fraction(start, self.tps)),
                    "end_s": float(Fraction(end, self.tps)),
                    "node_ids": nodes,
                    "lot_id": lot_id,
                }
            )
        )
        return start, end

    def walk(self, swap: int, source: str, target: str) -> None:
        if source == target:
            return
        metres = self.geo.distance(source, target)
        end = self.now + to_ticks(metres * self.walk_ticks_per_metre, 1)
        self._add(swap, "TRAVEL", "relocation_walk", end, self.geo.path(source, target), None)

    def handle(self, swap: int, node: str, operation: Operation, lot_id: str) -> tuple[int, int]:
        return self._add(
            swap, "BUSY_SERVICE", operation, self.now + self.handle_ticks, (node,), lot_id
        )


def _transfer(
    index: int,
    swap: int,
    step: int,
    lot: InitialLot,
    source: str,
    target: str,
    take: tuple[int, int],
    place: tuple[int, int],
) -> TransferRecord:
    return TransferRecord(
        transfer_id=f"RLT{index:05d}",
        swap_index=swap,
        step=step,
        lot_id=lot.lot_id,
        sku_id=lot.sku_id,
        quantity=lot.quantity,
        from_location=source,
        to_location=target,
        take_start_tick=take[0],
        take_end_tick=take[1],
        place_start_tick=place[0],
        place_end_tick=place[1],
    )


def _one_swap(
    line: _Timeline,
    swap: int,
    route: SwapRoute,
    lots: Mapping[str, InitialLot],
    first_transfer: int,
) -> list[TransferRecord]:
    first, second = route.first_slot, route.second_slot
    a, b = line.geo.service_node[first], line.geo.service_node[second]
    buffer, home = line.geo.buffer_node, line.geo.home_node
    lot_a, lot_b = lots[first], lots[second]
    line.walk(swap, home, a)
    take1 = line.handle(swap, a, "relocation_take", lot_a.lot_id)
    line.walk(swap, a, buffer)
    place1 = line.handle(swap, buffer, "relocation_place", lot_a.lot_id)
    line.walk(swap, buffer, b)
    take2 = line.handle(swap, b, "relocation_take", lot_b.lot_id)
    line.walk(swap, b, a)
    place2 = line.handle(swap, a, "relocation_place", lot_b.lot_id)
    line.walk(swap, a, buffer)
    take3 = line.handle(swap, buffer, "relocation_take", lot_a.lot_id)
    line.walk(swap, buffer, b)
    place3 = line.handle(swap, b, "relocation_place", lot_a.lot_id)
    line.walk(swap, b, home)
    n = first_transfer
    return [
        _transfer(n, swap, 1, lot_a, first, buffer, take1, place1),
        _transfer(n + 1, swap, 2, lot_b, second, first, take2, place2),
        _transfer(n + 2, swap, 3, lot_a, buffer, second, take3, place3),
    ]


def build_schedule(
    geo: PlanningGeometry,
    rates: WorkerRates,
    tps: int,
    routes: Sequence[SwapRoute],
    lots: Mapping[str, InitialLot],
) -> RelocationSchedule:
    """Sequential swaps by one worker; each swap starts and ends at the relocation home."""
    line = _Timeline(
        geo=geo,
        tps=tps,
        walk_ticks_per_metre=tps / rates.walk_speed_mps,
        handle_ticks=to_ticks(rates.take_or_place_s, tps),
    )
    transfers: list[TransferRecord] = []
    for index, route in enumerate(routes, start=1):
        transfers += _one_swap(line, index, route, lots, len(transfers) + 1)
    return RelocationSchedule(
        calendar="pre_shift",
        actor_id=RELOCATION_ACTOR_ID,
        ticks_per_second=tps,
        shift_start_s=0.0,
        window_ticks=line.now,
        window_s=float(Fraction(line.now, tps)),
        actions=tuple(line.actions),
        transfers=tuple(transfers),
    )
