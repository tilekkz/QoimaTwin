"""Static cover consistency; physical release and task completion remain unproved."""

from app.v3.staff_registry import StaffRegistry, validate_registry
from app.v3.staff_registry_values import typed_tuple
from app.v3.staffing_models import AnalyticalCover


def validate_covers(registry: StaffRegistry, covers: tuple[AnalyticalCover, ...]) -> None:
    validate_registry(registry)
    typed_tuple(covers, AnalyticalCover)
    workers = {w.actor_id: w for w in registry.workers}
    stations = {b.station_id: b.primary_actor_id for b in registry.station_bindings}
    ids: set[str] = set()
    for cover in covers:
        cover.__post_init__()
        if cover.cover_id in ids:
            raise ValueError("DUPLICATE_ANALYTICAL_COVER")
        ids.add(cover.cover_id)
        if cover.actor_id not in workers or cover.station_id not in stations:
            raise ValueError("UNKNOWN_ANALYTICAL_ACTOR_OR_STATION")
        worker = workers[cover.actor_id]
        if "pack" not in worker.eligible_roles or worker.primary_role == "pack":
            raise ValueError("ANALYTICAL_COVER_SKILL_REQUIRED")
        if any(
            w.actor_id == cover.actor_id
            and w.start_tick < cover.end_tick
            and cover.start_tick < w.end_tick
            for w in registry.unavailability
        ):
            raise ValueError("ANALYTICAL_HELPER_UNAVAILABLE")
        if not _primary_break_covers(registry, stations[cover.station_id], cover):
            raise ValueError("ANALYTICAL_PRIMARY_BREAK_REQUIRED")
    _overlaps(covers)


def _primary_break_covers(registry: StaffRegistry, primary: str, cover: AnalyticalCover) -> bool:
    cursor = cover.start_tick
    for window in sorted(registry.unavailability, key=lambda w: w.start_tick):
        if window.actor_id == primary and window.start_tick <= cursor < window.end_tick:
            cursor = window.end_tick
            if cursor >= cover.end_tick:
                return True
    return False


def _overlaps(covers: tuple[AnalyticalCover, ...]) -> None:
    for index, cover in enumerate(covers):
        for other in covers[index + 1 :]:
            shared = cover.actor_id == other.actor_id or cover.station_id == other.station_id
            overlap = cover.start_tick < other.end_tick and other.start_tick < cover.end_tick
            if shared and overlap:
                raise ValueError("OVERLAPPING_ANALYTICAL_ASSIGNMENT")
