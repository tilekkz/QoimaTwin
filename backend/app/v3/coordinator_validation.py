"""Strict B1 registration, declared common calendar and directed role routes."""

from app.v3.coordinator_models import CoordinatorProfile, RoleIntent, RoleStation
from app.v3.runtime_graph import CandidateRoute, RouteRequirements
from app.v3.runtime_time import operation_ticks
from app.v3.staff_registry import validate_registry
from app.v3.staff_registry_values import period, text, tick, typed_tuple


def validate_profile(profile: CoordinatorProfile) -> None:
    if type(profile) is not CoordinatorProfile:
        raise ValueError("COORDINATOR_PROFILE_REQUIRED")
    text(profile.profile_id)
    text(profile.provenance)
    source = validate_registry(profile.registry)
    typed_tuple(profile.stations, RoleStation)
    typed_tuple(profile.intents, RoleIntent)
    stations = {s.station_id: s for s in profile.stations}
    if len(profile.stations) != 6 or set(stations) != {s.station_id for s in source.stations}:
        raise ValueError("COORDINATOR_SIX_STATIONS_REQUIRED")
    flow = profile.world.receipts.flow
    actual = stations.get(flow.station.station_id)
    primary = {b.station_id: b.primary_actor_id for b in profile.registry.station_bindings}
    if (
        actual is None
        or (actual.node_id, actual.bench_owner) != (flow.station.node, flow.station.bench_owner)
        or primary.get(flow.station.station_id) != flow.packer_id
    ):
        raise ValueError("ROLE_STATION_BINDING_MISMATCH")
    owners = {o.owner_id: o for o in flow.stock.owners + flow.owners}
    for station in stations.values():
        for value in (station.station_id, station.node_id, station.bench_owner):
            text(value)
        if station.node_id not in flow.graph.node_ids:
            raise ValueError("UNKNOWN_ROLE_STATION_NODE")
        if station.bench_owner not in owners or owners[station.bench_owner].capacity != 1:
            raise ValueError("EXCLUSIVE_ROLE_BENCH_REQUIRED")
        if owners[station.bench_owner].kind != "workstation":
            raise ValueError("ROLE_BENCH_KIND_REQUIRED")
    if (
        len({s.node_id for s in stations.values()}) != 6
        or len({s.bench_owner for s in stations.values()}) != 6
    ):
        raise ValueError("ROLE_STATIONS_MUST_BE_DISTINCT")
    _intents(profile)


def _intents(profile: CoordinatorProfile) -> None:
    workers = {w.actor_id: w for w in profile.registry.workers}
    primary = {s.station_id: s.primary_actor_id for s in profile.registry.station_bindings}
    ids: set[str] = set()
    business = {o.order_id for o in profile.world.receipts.flow.orders} | {
        o.job_id for o in profile.world.orders
    }
    business.update(r.definition.receipt_id for r in profile.world.receipts.receipts)
    for intent in profile.intents:
        _intent_types(intent)
        if intent.intent_id in ids | business:
            raise ValueError("DUPLICATE_COORDINATOR_WORK_ID")
        ids.add(intent.intent_id)
        if intent.actor_id not in workers or intent.station_id not in primary:
            raise ValueError("UNKNOWN_ROLE_INTENT_REFERENCE")
        worker = workers[intent.actor_id]
        actor = next(a for a in profile.world.receipts.flow.actors if a.actor_id == intent.actor_id)
        if intent.restore_node != actor.home:
            raise ValueError("ROLE_RESTORE_HOME_REQUIRED")
        if worker.primary_role == "pack" or "pack" not in worker.eligible_roles:
            raise ValueError("EXPLICIT_CROSS_TRAINING_REQUIRED")
        if not _covered(
            profile, primary[intent.station_id], intent.request_tick, intent.restore_by_tick
        ):
            raise ValueError("COMMON_PRIMARY_BREAK_REQUIRED")
        if any(
            w.actor_id == intent.actor_id
            and w.start_tick < intent.restore_by_tick
            and intent.request_tick < w.end_tick
            for w in profile.registry.unavailability
        ):
            raise ValueError("ROLE_HELPER_UNAVAILABLE")
        role_route(profile, intent.actor_id, intent.restore_node, _station_node(profile, intent))
        role_route(profile, intent.actor_id, _station_node(profile, intent), intent.restore_node)
    _overlaps(profile.intents)


def _intent_types(intent: RoleIntent) -> None:
    for value in (intent.intent_id, intent.actor_id, intent.station_id, intent.restore_node):
        text(value)
    period(intent.request_tick, intent.return_tick)
    period(intent.return_tick, intent.restore_by_tick)


def _covered(profile: CoordinatorProfile, actor: str, start: int, end: int) -> bool:
    cursor = start
    for window in sorted(profile.registry.unavailability, key=lambda w: w.start_tick):
        if window.actor_id == actor and window.start_tick <= cursor < window.end_tick:
            cursor = window.end_tick
    return cursor >= end


def _station_node(profile: CoordinatorProfile, intent: RoleIntent) -> str:
    return next(s.node_id for s in profile.stations if s.station_id == intent.station_id)


def _overlaps(intents: tuple[RoleIntent, ...]) -> None:
    for index, left in enumerate(intents):
        for right in intents[index + 1 :]:
            shared = left.actor_id == right.actor_id or left.station_id == right.station_id
            if (
                shared
                and left.request_tick < right.restore_by_tick
                and right.request_tick < left.restore_by_tick
            ):
                raise ValueError("OVERLAPPING_ROLE_INTENTS")


def role_route(
    profile: CoordinatorProfile, actor_id: str, start: str, end: str
) -> tuple[int, CandidateRoute]:
    actor = next(a for a in profile.world.receipts.flow.actors if a.actor_id == actor_id)
    route = profile.world.receipts.flow.graph.shortest_path(
        start, end, RouteRequirements(mode="pedestrian")
    )
    if route is None:
        raise ValueError("MISSING_DIRECTED_ROLE_ROUTE")
    return operation_ticks(route.length_m / actor.speed_m_s), route


def validate_horizon(profile: CoordinatorProfile, horizon: int, end: int) -> None:
    if not 0 < tick(horizon) <= tick(end):
        raise ValueError("POSITIVE_COORDINATOR_HORIZON_REQUIRED")
    if any(i.request_tick >= horizon for i in profile.intents):
        raise ValueError("ROLE_REQUEST_MUST_BE_BEFORE_HORIZON")
