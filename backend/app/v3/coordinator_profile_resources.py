"""Bind six source stations and source parcel ports without inventing travel geometry."""

from fractions import Fraction
from typing import Any

from app.v3.conveyor_models import ConveyorSource
from app.v3.coordinator_units_models import (
    GoodsStation,
    ParcelPort,
    PickerBinding,
    UnitAssignment,
    UnitCart,
    UnitResources,
)
from app.v3.flow_profile_decode import rational
from app.v3.input_models import V3Bundle
from app.v3.light_flow_models import FlowCart, FlowPort, FlowStation
from app.v3.light_flow_source import _path
from app.v3.runtime_time import operation_ticks
from app.v3.staff_registry import StaffRegistry


def resources(
    bundle: V3Bundle,
    conveyor: ConveyorSource,
    value: dict[str, Any],
    registry: StaffRegistry,
) -> UnitResources:
    primary = {b.station_id: b.primary_actor_id for b in registry.station_bindings}
    return UnitResources(
        tuple(_station(conveyor, row, primary) for row in value["goods_stations"]),
        tuple(_cart(row) for row in value["carts"]),
        tuple(
            PickerBinding(row["actor_id"], tuple(row["cart_ids"]))
            for row in value["picker_bindings"]
        ),
        tuple(_port(bundle, row) for row in value["parcel_ports"]),
        tuple(UnitAssignment(**row) for row in value["unit_assignments"]),
    )


def _station(
    conveyor: ConveyorSource,
    row: dict[str, Any],
    primary: dict[str, str],
) -> GoodsStation:
    key = row["station_id"]
    if key not in conveyor.stations or key not in primary:
        raise ValueError("Unknown source/registry station")
    work = conveyor.stations[key].work_node_id
    route = _path(conveyor, conveyor.edges["v3:conv:feed"].source, work)
    route += _path(conveyor, work, conveyor.edges["v3:conv:main-tail"].target)
    return GoodsStation(
        FlowStation(key, "v3:service:" + key, row["bench_owner"], row["empty_owner"]),
        route,
        primary[key],
        row["package_pool_owner"],
    )


def _cart(row: dict[str, Any]) -> UnitCart:
    return UnitCart(
        FlowCart(
            row["cart_id"],
            row["home"],
            "v3:service:CART_PARK",
            row["owner_id"],
            rational(row["speed_m_s"]),
            rational(row["max_gross_kg"]),
            rational(row["width_m"]),
        ),
        row["carrier_pool_owner"],
        row["release_tick"],
    )


def _port(bundle: V3Bundle, row: dict[str, Any]) -> ParcelPort:
    source = next((p for p in bundle.ports if p.port_id == row["port_id"]), None)
    if source is None or source.direction != "outbound":
        raise ValueError("Parcel port must be a source outbound port")
    seconds = dict(source.seconds_by_archetype).get("SMALL_CARTON")
    if seconds is None:
        raise ValueError("Source port does not support SMALL parcels")
    windows = tuple(
        (operation_ticks(Fraction(str(a))), operation_ticks(Fraction(str(b))))
        for a, b in source.open_windows
    )
    return ParcelPort(
        FlowPort(
            source.port_id, source.service_node_id, operation_ticks(Fraction(str(seconds))), windows
        ),
        row["shipped_owner"],
    )
