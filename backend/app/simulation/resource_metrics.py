"""Time integrals of finite resources; normal tick dwell is not a capacity jam."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from app.simulation.observations import ResourceSample

if TYPE_CHECKING:
    from app.simulation.engine import Engine


def intervals(samples: list[ResourceSample], cutoff: int) -> list[tuple[ResourceSample, int]]:
    result = []
    for index, sample in enumerate(samples):
        end = samples[index + 1].at_tick if index + 1 < len(samples) else cutoff
        width = max(0, min(end, cutoff) - sample.at_tick)
        if width:
            result.append((sample, width))
    return result


def resource_summary(engine: Engine, cutoff: int) -> dict[str, Any]:
    rows = intervals(engine.observer.samples, cutoff)
    tps, total = engine.ctx.grid.ticks_per_second, engine.ctx.config.totes_total

    def area(value: Callable[[ResourceSample], int]) -> int:
        return sum(value(sample) * width for sample, width in rows)

    occupied = area(lambda s: s.occupied_cells)
    free = area(lambda s: s.free_totes)
    return {
        "conveyor_metrics": {
            "occupied_cells_mean": occupied / cutoff if cutoff else None,
            "occupancy_ratio": occupied / (cutoff * len(engine.ctx.topology.cells))
            if cutoff
            else None,
            "occupied_cells_max": max((s.occupied_cells for s, _ in rows), default=0),
            "jam_duration_s": area(lambda s: int(s.jammed_cells > 0)) / tps,
            "blocked_cargo_seconds": area(lambda s: s.jammed_cells) / tps,
        },
        "tote_metrics": {
            "total": total,
            "free_mean": free / cutoff if cutoff else None,
            "free_min": min((s.free_totes for s, _ in rows), default=total),
            "allocated_mean": total - free / cutoff if cutoff else None,
            "availability_ratio": free / (cutoff * total) if cutoff else None,
            "unavailable_s": area(lambda s: int(s.free_totes == 0)) / tps,
        },
        "receiving_metrics": {
            "area_mean": area(lambda s: s.receiving_area) / cutoff if cutoff else None,
            "area_max": max((s.receiving_area for s, _ in rows), default=0),
        },
    }
