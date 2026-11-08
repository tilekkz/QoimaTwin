"""Observed service and conservative reservation exposure by declared port and cargo class."""

from app.v3.coordinator_metrics_values import ratio
from app.v3.coordinator_models import CoordinatorOutcome, CoordinatorProfile, CoordinatorSnapshot
from app.v3.coordinator_units import order_views
from app.v3.interface import Json


def open_ticks(windows: tuple[tuple[int, int], ...], tick: int) -> int:
    total, until = 0, 0
    for start, end in sorted(windows):
        left, right = max(until, start), min(tick, end)
        total += max(0, right - left)
        until = max(until, right)
    return total


def ports(
    profile: CoordinatorProfile, outcome: CoordinatorOutcome, point: CoordinatorSnapshot
) -> list[Json]:
    definitions = _definitions(profile)
    rows: dict[tuple[str, str, str], Json] = {}
    for key, (_, _, _, windows) in definitions.items():
        port, kind, cargo, _ = definitions[key]
        identity = (port, kind, cargo)
        rows.setdefault(
            identity,
            {
                "port_id": port,
                "work_kind": kind,
                "cargo_class": cargo,
                "open_ticks": open_ticks(windows, point.tick),
                "service_ticks": 0,
                "reservation_ticks": 0,
                "completed_jobs": 0,
                "completed_units": 0,
            },
        )
    for event in outcome.events:
        operation = event.operation
        if (
            event.kind != "operation_started"
            or operation is None
            or operation.kind not in {"receipt_service", "whole_service", "shipping_service"}
            or event.tick >= point.tick
        ):
            continue
        port, kind, cargo, _ = definitions[event.order_id]
        row = rows[port, kind, cargo]
        duration = min(point.tick, operation.planned_end_tick) - event.tick
        row["service_ticks"] += duration
        if kind != "whole_hu":
            row["reservation_ticks"] += duration
    _completed(profile, point, definitions, rows)
    for row in rows.values():
        row["service_fraction"] = ratio(row["service_ticks"], row["open_ticks"])
        row["reservation_fraction"] = ratio(row["reservation_ticks"], row["open_ticks"])
    return [rows[key] for key in sorted(rows)]


def _definitions(
    profile: CoordinatorProfile,
) -> dict[str, tuple[str, str, str, tuple[tuple[int, int], ...]]]:
    flow = profile.world.receipts.flow
    cargo = {u.origin_hu: u.recipe.archetype_id for u in flow.stock.units}
    sku = {u.sku_id: u.recipe.archetype_id for u in flow.stock.units}
    receipt_ports = {p.port_id: p for p in profile.world.receipts.ports}
    result = {}
    for offer in profile.world.receipts.receipts:
        archetype = sku[offer.definition.sku_id]
        cargo[offer.definition.hu_id] = archetype
        result[offer.definition.receipt_id] = (
            offer.port_id,
            "receipt",
            archetype,
            receipt_ports[offer.port_id].windows,
        )
    whole_ports = {p.port_id: p for p in profile.world.ports}
    for order in profile.world.orders:
        result[order.job_id] = (
            order.port_id,
            "whole_hu",
            cargo[order.hu_id],
            whole_ports[order.port_id].windows,
        )
    for key, view in order_views(profile).items():
        result[key] = (view.port.port_id, "unit_parcel", "sealed_parcel", view.port.windows)
    return result


def _completed(
    profile: CoordinatorProfile,
    point: CoordinatorSnapshot,
    definitions: dict[str, tuple[str, str, str, tuple[tuple[int, int], ...]]],
    rows: dict[tuple[str, str, str], Json],
) -> None:
    quantities: dict[str, int] = {}
    for unit in profile.world.receipts.flow.stock.units:
        quantities[unit.origin_hu] = quantities.get(unit.origin_hu, 0) + 1
    for offer in profile.world.receipts.receipts:
        quantities[offer.definition.hu_id] = offer.definition.quantity_units
    whole = {o.job_id: o for o in profile.world.orders}
    for view in point.whole_orders:
        row = rows[definitions[view.job_id][:3]]
        if view.port_reserved_tick is not None:
            end = point.tick if view.shipped_tick is None else view.shipped_tick
            row["reservation_ticks"] += min(point.tick, end) - view.port_reserved_tick
        if view.shipped_tick is not None:
            row["completed_jobs"] += 1
            row["completed_units"] += quantities[whole[view.job_id].hu_id]
    units = {o.order_id: o for o in profile.world.receipts.flow.orders}
    for order in point.orders:
        if order.shipped_tick is not None:
            row = rows[definitions[order.order_id][:3]]
            row["completed_jobs"] += 1
            row["completed_units"] += len(units[order.order_id].package_placements)
    offers = {o.definition.receipt_id: o for o in profile.world.receipts.receipts}
    for receipt in point.receipts:
        if receipt.credited_tick is not None:
            row = rows[definitions[receipt.receipt_id][:3]]
            row["completed_jobs"] += 1
            row["completed_units"] += offers[receipt.receipt_id].definition.quantity_units
