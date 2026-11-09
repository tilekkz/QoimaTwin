"""Pure schedule exposures. No clock, live grant, worker map or N4 execution is created."""

from itertools import pairwise

from app.v3.staff_registry import StaffRegistry
from app.v3.staff_registry_models import WorkerCapability
from app.v3.staff_registry_values import ROLES, Role, role, tick
from app.v3.staffing_models import AnalyticalCover, StaffingExposure
from app.v3.staffing_validation import validate_covers


def analyze_staffing(
    registry: StaffRegistry, covers: tuple[AnalyticalCover, ...], start_tick: int, end_tick: int
) -> StaffingExposure:
    validate_covers(registry, covers)
    if tick(start_tick) > tick(end_tick):
        raise ValueError("REVERSED_STAFFING_WINDOW")
    totals = dict.fromkeys((*ROLES, "transition", "unavailable"), 0)
    boundaries = {start_tick, end_tick}
    for window in registry.unavailability:
        boundaries.update((window.start_tick, window.end_tick))
    for cover in covers:
        boundaries.update(
            (
                cover.start_tick,
                cover.start_tick + cover.outward_ticks,
                cover.end_tick - cover.return_ticks,
                cover.end_tick,
            )
        )
    clipped = sorted(t for t in boundaries if start_tick <= t <= end_tick)
    for start, end in pairwise(clipped):
        for worker in registry.workers:
            totals[_state(registry, covers, worker, start)] += end - start
    return StaffingExposure(
        start_tick,
        end_tick,
        tuple((r, totals[r]) for r in ROLES),
        totals["transition"],
        totals["unavailable"],
        len(registry.workers) * (end_tick - start_tick),
    )


def schedule_eligible_actor_ids(
    registry: StaffRegistry, covers: tuple[AnalyticalCover, ...], requested_role: Role, at_tick: int
) -> tuple[str, ...]:
    validate_covers(registry, covers)
    tick(at_tick)
    role(requested_role)
    return tuple(
        sorted(
            w.actor_id
            for w in registry.workers
            if _state(registry, covers, w, at_tick) == requested_role
        )
    )


def _state(
    registry: StaffRegistry,
    covers: tuple[AnalyticalCover, ...],
    worker: WorkerCapability,
    at_tick: int,
) -> str:
    if any(
        w.actor_id == worker.actor_id and w.start_tick <= at_tick < w.end_tick
        for w in registry.unavailability
    ):
        return "unavailable"
    for cover in covers:
        if cover.actor_id == worker.actor_id and cover.start_tick <= at_tick < cover.end_tick:
            if (
                cover.start_tick + cover.outward_ticks
                <= at_tick
                < cover.end_tick - cover.return_ticks
            ):
                return "pack"
            return "transition"
    return worker.primary_role
