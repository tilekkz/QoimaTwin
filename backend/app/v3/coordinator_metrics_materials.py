"""Actual empty material counts and exact count-time areas; no implicit replenishment."""

from collections import Counter, defaultdict

from app.storage.canonical_json import canonical_bytes
from app.v3.coordinator_metrics_values import ratio
from app.v3.coordinator_models import CoordinatorOutcome, CoordinatorProfile, CoordinatorSnapshot
from app.v3.flow_profile_wire import record
from app.v3.interface import Json
from app.v3.stock_models import Container, StockDelta

MaterialState = dict[str, tuple[Container, int]]


def _changes(outcome: CoordinatorOutcome, cutoff: int) -> dict[int, list[StockDelta]]:
    result: dict[int, list[StockDelta]] = defaultdict(list)
    for event in outcome.events:
        if event.tick <= cutoff and event.delta is not None:
            result[event.tick].append(event.delta)
    return result


def _apply(state: MaterialState, delta: StockDelta) -> None:
    for before in delta.before:
        key = before.container.container_id
        if key in state and canonical_bytes(record(state[key])) != canonical_bytes(
            record(
                (
                    before.container,
                    len(before.units),
                )
            )
        ):
            raise ValueError("KPI material delta does not follow observed state")
    for after in delta.after:
        key = after.container.container_id
        if key in state:
            state[key] = after.container, len(after.units)


def _reserved(profile: CoordinatorProfile, point: CoordinatorSnapshot, tick: int) -> set[str]:
    orders = {o.order_id: o for o in profile.world.receipts.flow.orders}
    result: set[str] = set()
    for view in point.orders:
        if view.order_id not in orders:
            raise ValueError("KPI unknown order material binding")
        if (
            view.admitted_tick is not None
            and view.admitted_tick <= tick
            and (view.shipped_tick is None or tick < view.shipped_tick)
        ):
            order = orders[view.order_id]
            result.update((order.carrier_id, order.package_id))
    return result


def _counts(state: MaterialState, reserved: set[str]) -> tuple[Counter[str], Counter[str]]:
    physical: Counter[str] = Counter()
    available: Counter[str] = Counter()
    for key, (container, units) in state.items():
        physical[container.owner_id] += 1
        if units == 0 and container.sealed_for is None and key not in reserved:
            available[container.owner_id] += 1
    return physical, available


def _rows(profile: CoordinatorProfile) -> dict[str, Json]:
    flow = profile.world.receipts.flow
    racks = (
        {s.station.empty_owner for s in profile.unit_resources.stations}
        if profile.unit_resources is not None
        else {flow.station.empty_owner}
    )
    return {
        o.owner_id: {
            "owner_id": o.owner_id,
            "kind": o.kind,
            "capacity": o.capacity,
            "container_ticks": 0,
            "free_place_ticks": 0,
            "empty_unbound_container_ticks": 0,
            "zero_empty_unbound_ticks": 0,
        }
        for o in (*flow.stock.owners, *flow.owners)
        if o.kind == "material" or o.owner_id in racks
    }


def _endpoint(state: MaterialState, point: CoordinatorSnapshot) -> None:
    quantities = Counter(location.container_id for location in point.stock.locations)
    actual = {
        c.container_id: (c, quantities[c.container_id])
        for c in point.stock.containers
        if c.recipe.kind in {"carrier", "package"}
    }
    if canonical_bytes(record(state)) != canonical_bytes(record(actual)):
        raise ValueError("KPI material journal differs from captured inventory")


def _accumulate(
    rows: dict[str, Json],
    state: MaterialState,
    reserved: set[str],
    width: int,
) -> None:
    physical, empty = _counts(state, reserved)
    for owner, row in rows.items():
        if physical[owner] > row["capacity"]:
            raise ValueError("KPI observed material owner exceeds capacity")
        row["container_ticks"] += physical[owner] * width
        row["free_place_ticks"] += (row["capacity"] - physical[owner]) * width
        row["empty_unbound_container_ticks"] += empty[owner] * width
        row["zero_empty_unbound_ticks"] += width if empty[owner] == 0 else 0
        row["current_containers"] = physical[owner]
        row["current_free_places"] = row["capacity"] - physical[owner]
        row["current_empty_unbound_containers"] = empty[owner]


def materials(
    profile: CoordinatorProfile,
    outcome: CoordinatorOutcome,
    point: CoordinatorSnapshot,
) -> list[Json]:
    state: MaterialState = {c.container_id: (c, 0) for c in profile.world.receipts.flow.materials}
    rows = _rows(profile)
    changes = _changes(outcome, point.tick)
    boundaries = {0, point.tick, *changes}
    boundaries.update(
        t
        for o in point.orders
        for t in (o.admitted_tick, o.shipped_tick)
        if t is not None and t <= point.tick
    )
    ticks = sorted(boundaries)
    for index, tick in enumerate(ticks):
        for delta in changes.get(tick, []):
            _apply(state, delta)
        width = ticks[index + 1] - tick if index + 1 < len(ticks) else 0
        _accumulate(rows, state, _reserved(profile, point, tick), width)
    _endpoint(state, point)
    for row in rows.values():
        row["mean_containers"] = ratio(row["container_ticks"], point.tick)
        row["mean_free_places"] = ratio(row["free_place_ticks"], point.tick)
        row["mean_empty_unbound_containers"] = ratio(
            row["empty_unbound_container_ticks"], point.tick
        )
        row["availability_scope"] = "empty_unsealed_here_not_bound_to_unshipped_admitted_order"
    return [rows[key] for key in sorted(rows)]
