"""Exact integer time grid (ADR 0002).

All engine times are integer ticks. The grid resolution is the least common multiple of a base
resolution and the denominators of every primitive duration, so every primitive duration is an
exact integer.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction

from app.contracts.base import exact
from app.contracts.config import SimulationConfig
from app.contracts.layout import Graph, Layout

BASE_TICKS_PER_SECOND = 1_000_000
MAX_TICKS_PER_SECOND = 1_000_000_000


class TimeGridError(ValueError):
    """A duration cannot be represented exactly on the grid, or the grid is too fine."""


def _edge_times(graph: Graph, speed: Fraction) -> list[Fraction]:
    return [exact(edge.length_m) / speed for edge in graph.edges]


def primitive_durations(layout: Layout, config: SimulationConfig) -> list[Fraction]:
    """Every elementary duration the engine adds up: edge walks/drives and service components."""
    walk = exact(config.walk_speed_mps)
    drive = exact(config.forklift_speed_mps)
    cell = exact(config.conveyor_cell_m) / exact(config.conveyor_speed_mps)
    durations = _edge_times(layout.picker_graph, walk)
    durations += _edge_times(layout.forklift_graphs.inbound, drive)
    durations += _edge_times(layout.forklift_graphs.outbound, drive)
    durations.append(cell)
    durations += [
        exact(value)
        for value in (
            config.pick_base_s,
            config.pick_per_unit_s,
            config.handoff_s,
            config.pack_base_s,
            config.pack_per_line_s,
            config.pack_per_unit_s,
            config.conveyor_tick_s,
            config.receive_service_s,
            config.forklift_pickup_s,
            config.forklift_drop_s,
            config.shipping_scan_s,
            config.pallet_max_age_s,
            config.relocation_take_or_place_s,
            config.max_drain_s,
            config.snapshot_interval_s,
            config.chunk_duration_s,
        )
    ]
    return durations


@dataclass(frozen=True, slots=True)
class TimeGrid:
    ticks_per_second: int

    @classmethod
    def from_durations(cls, durations: Iterable[Fraction]) -> TimeGrid:
        tps = BASE_TICKS_PER_SECOND
        for duration in durations:
            tps = math.lcm(tps, Fraction(duration).denominator)
        if tps > MAX_TICKS_PER_SECOND:
            raise TimeGridError(f"time grid would need {tps} ticks per second")
        return cls(ticks_per_second=tps)

    @classmethod
    def for_inputs(cls, layout: Layout, config: SimulationConfig) -> TimeGrid:
        return cls.from_durations(primitive_durations(layout, config))

    def ticks(self, seconds: Fraction) -> int:
        """Exact tick count of a non-negative duration; raises if it is not on the grid."""
        value = Fraction(seconds) * self.ticks_per_second
        if value < 0:
            raise TimeGridError(f"negative duration {seconds} s")
        if value.denominator != 1:
            raise TimeGridError(f"{seconds} s is not representable at {self.ticks_per_second}/s")
        return value.numerator

    def seconds(self, ticks: int) -> Fraction:
        return Fraction(ticks, self.ticks_per_second)

    def to_seconds_float(self, ticks: int) -> float:
        """Seconds for export; the nearest double to the exact value."""
        return float(self.seconds(ticks))

    def ceil_to_second(self, ticks: int) -> int:
        """First integer-second tick at or after `ticks` (conveyor admission boundary)."""
        tps = self.ticks_per_second
        return -(-ticks // tps) * tps
