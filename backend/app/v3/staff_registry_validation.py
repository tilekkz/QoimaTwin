"""Recheck nested runtime types and source membership, including retained immutable values."""

from collections.abc import Mapping

from app.v3.staff_registry_models import (
    StaffSource,
    StationBinding,
    Unavailability,
    WorkerCapability,
)
from app.v3.staff_registry_values import typed_tuple


def validate_registry_inputs(
    workers: tuple[WorkerCapability, ...],
    windows: tuple[Unavailability, ...],
    bindings: tuple[StationBinding, ...],
    source: StaffSource,
) -> None:
    typed_tuple(workers, WorkerCapability)
    typed_tuple(windows, Unavailability)
    typed_tuple(bindings, StationBinding)
    for worker in workers:
        worker.__post_init__()
    for window in windows:
        window.__post_init__()
    for binding in bindings:
        binding.__post_init__()
    actor_ids = [w.actor_id for w in workers]
    if len(actor_ids) != len(set(actor_ids)) or set(actor_ids) != set(source.actor_ids):
        raise ValueError("STAFF_SOURCE_ROSTER_MISMATCH")
    primary_roles, vehicles = dict(source.primary_roles), dict(source.forklift_pairs)
    for worker in workers:
        if worker.primary_role != primary_roles[worker.actor_id]:
            raise ValueError("STAFF_PRIMARY_SOURCE_ROLE_MISMATCH")
        allowed = {"manual_cart"} | (
            {vehicles[worker.actor_id]} if worker.actor_id in vehicles else set()
        )
        if not set(worker.permitted_equipment) <= allowed:
            raise ValueError("STAFF_SOURCE_VEHICLE_PAIR_MISMATCH")
        if "forklift" in worker.eligible_roles and not any(
            e.startswith("FL") for e in worker.permitted_equipment
        ):
            raise ValueError("STAFF_REQUIRED_EQUIPMENT_MISSING")
    _windows(windows, set(actor_ids))
    _bindings(bindings, primary_roles, source)


def _windows(windows: tuple[Unavailability, ...], actors: set[str]) -> None:
    last: dict[str, int] = {}
    for window in sorted(windows, key=lambda w: (w.actor_id, w.start_tick)):
        if window.actor_id not in actors:
            raise ValueError("UNKNOWN_STAFF_WINDOW_ACTOR")
        if window.start_tick < last.get(window.actor_id, 0):
            raise ValueError("OVERLAPPING_UNAVAILABILITY")
        last[window.actor_id] = window.end_tick


def _bindings(
    bindings: tuple[StationBinding, ...], roles: Mapping[str, str], source: StaffSource
) -> None:
    ids = [b.station_id for b in bindings]
    if len(ids) != len(set(ids)) or set(ids) != {s.station_id for s in source.stations}:
        raise ValueError("STAFF_SOURCE_STATIONS_MISMATCH")
    primaries = [b.primary_actor_id for b in bindings]
    if len(primaries) != len(set(primaries)) or any(
        roles.get(actor) != "pack" for actor in primaries
    ):
        raise ValueError("STAFF_PRIMARY_STATION_BINDINGS_MISMATCH")
