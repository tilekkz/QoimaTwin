"""Explicit common resources and allocation for concurrent unit workflows."""

from dataclasses import dataclass

from app.v3.light_flow_models import FlowCart, FlowPort, FlowStation


@dataclass(frozen=True, slots=True)
class GoodsStation:
    station: FlowStation
    belt_route: tuple[str, ...]
    primary_id: str
    package_pool_owner: str


@dataclass(frozen=True, slots=True)
class UnitCart:
    cart: FlowCart
    carrier_pool_owner: str
    release_tick: int


@dataclass(frozen=True, slots=True)
class PickerBinding:
    actor_id: str
    cart_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ParcelPort:
    port: FlowPort
    shipped_owner: str


@dataclass(frozen=True, slots=True)
class UnitAssignment:
    order_id: str
    picker_id: str
    cart_id: str
    station_id: str
    shipper_id: str
    port_id: str


@dataclass(frozen=True, slots=True)
class UnitResources:
    stations: tuple[GoodsStation, ...]
    carts: tuple[UnitCart, ...]
    pickers: tuple[PickerBinding, ...]
    ports: tuple[ParcelPort, ...]
    assignments: tuple[UnitAssignment, ...]
