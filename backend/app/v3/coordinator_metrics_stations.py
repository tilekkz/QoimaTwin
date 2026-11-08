"""Six physical stations: pack/clear service is distinct from bench and worker ownership."""

from app.v3.coordinator_metrics_observed_values import elapsed, no_overlap
from app.v3.coordinator_metrics_values import integer, ratio
from app.v3.coordinator_models import CoordinatorOutcome, CoordinatorProfile, CoordinatorSnapshot
from app.v3.coordinator_packing_models import PackingView
from app.v3.interface import Json


def _reservations(rows: dict[str, Json], point: CoordinatorSnapshot) -> dict[str, PackingView]:
    intervals: dict[str, list[tuple[int, int]]] = {key: [] for key in rows}
    packing = {view.order_id: view for view in point.packing}
    if len(packing) != len(point.packing):
        raise ValueError("KPI duplicate packing job")
    for view in point.packing:
        if view.station_id not in rows or integer(view.assigned_tick) > point.tick:
            raise ValueError("KPI packing station/assignment differs")
        for tick in (view.packed_tick, view.cleared_tick, view.released_tick):
            if tick is not None and not view.assigned_tick <= integer(tick) <= point.tick:
                raise ValueError("KPI packing completion exceeds observed boundary")
        row = rows[view.station_id]
        held = elapsed(view.assigned_tick, view.cleared_tick, point.tick)
        intervals[view.station_id].append((view.assigned_tick, view.assigned_tick + held))
        row["bench_reserved_ticks"] += held
        row["current_bench_reserved"] += int(view.cleared_tick is None)
        row["packed_orders"] += int(view.packed_tick is not None)
        row["cleared_orders"] += int(view.cleared_tick is not None)
    for values in intervals.values():
        no_overlap(values)
    return packing


def _service(
    rows: dict[str, Json],
    packing: dict[str, PackingView],
    outcome: CoordinatorOutcome,
    point: CoordinatorSnapshot,
) -> None:
    intervals: dict[str, list[tuple[int, int]]] = {key: [] for key in rows}
    for event in outcome.events:
        op = event.operation
        if (
            event.kind != "operation_started"
            or op is None
            or op.kind not in {"pack", "clear"}
            or event.tick >= point.tick
        ):
            continue
        view = packing.get(event.order_id)
        if view is None or view.actor_id != event.actor_id or op.start_tick != event.tick:
            raise ValueError("KPI pack service lacks actual packing assignment")
        duration = elapsed(op.start_tick, op.planned_end_tick, point.tick)
        end = op.start_tick + duration
        if op.start_tick < view.assigned_tick or (
            view.cleared_tick is not None and end > view.cleared_tick
        ):
            raise ValueError("KPI service escapes actual station reservation")
        intervals[view.station_id].append((op.start_tick, end))
        rows[view.station_id][op.kind + "_service_ticks"] += duration
    for values in intervals.values():
        no_overlap(values)


def stations(
    profile: CoordinatorProfile,
    outcome: CoordinatorOutcome,
    point: CoordinatorSnapshot,
) -> list[Json]:
    rows: dict[str, Json] = {
        s.station_id: {
            "station_id": s.station_id,
            "pack_service_ticks": 0,
            "clear_service_ticks": 0,
            "bench_reserved_ticks": 0,
            "packed_orders": 0,
            "cleared_orders": 0,
            "current_bench_reserved": 0,
        }
        for s in profile.stations
    }
    packing = _reservations(rows, point)
    _service(rows, packing, outcome, point)
    for row in rows.values():
        service = row["pack_service_ticks"] + row["clear_service_ticks"]
        if service > row["bench_reserved_ticks"]:
            raise ValueError("KPI station service exceeds physical reservation")
        row["service_fraction"] = ratio(service, point.tick)
        row["bench_reserved_fraction"] = ratio(row["bench_reserved_ticks"], point.tick)
    return [rows[key] for key in sorted(rows)]
