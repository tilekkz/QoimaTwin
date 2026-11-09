"""Strict resource registration is distinct from runtime permission to start work."""

from fractions import Fraction
from itertools import pairwise

from app.v3.belt_plan import valid_tick
from app.v3.conveyor_models import ConveyorSource
from app.v3.coordinator_models import CoordinatorProfile
from app.v3.coordinator_units_models import (
    GoodsStation,
    ParcelPort,
    PickerBinding,
    UnitAssignment,
    UnitCart,
    UnitResources,
)
from app.v3.light_flow_models import FlowCart, FlowPort, FlowStation
from app.v3.receipt_flow_models import ReceiptPort
from app.v3.receipt_flow_validate import _windows
from app.v3.staff_registry_values import text, typed_tuple


def validate_resources(profile: CoordinatorProfile, conveyor: ConveyorSource) -> None:
    resource = profile.unit_resources
    if resource is None:
        return
    if type(resource) is not UnitResources:
        raise ValueError("TYPED_UNIT_RESOURCES_REQUIRED")
    for values, kind in (
        (resource.stations, GoodsStation),
        (resource.carts, UnitCart),
        (resource.pickers, PickerBinding),
        (resource.ports, ParcelPort),
        (resource.assignments, UnitAssignment),
    ):
        typed_tuple(values, kind)
    _stations(profile, resource, conveyor)
    _carts(profile, resource)
    _ports(profile, resource)
    _assignments(profile, resource)
    _default_aliases(profile, resource)


def _stations(p: CoordinatorProfile, r: UnitResources, c: ConveyorSource) -> None:
    if any(type(s.station) is not FlowStation for s in r.stations):
        raise ValueError("TYPED_GOODS_STATION_REQUIRED")
    role = {s.station_id: s for s in p.stations}
    primary = {b.station_id: b.primary_actor_id for b in p.registry.station_bindings}
    if len(r.stations) != 6 or {s.station.station_id for s in r.stations} != set(role):
        raise ValueError("SIX_GOODS_STATIONS_REQUIRED")
    physical: set[str] = set()
    for value in r.stations:
        s = value.station
        if (
            type(s) is not FlowStation
            or (s.node, s.bench_owner)
            != (
                role[s.station_id].node_id,
                role[s.station_id].bench_owner,
            )
            or value.primary_id != primary[s.station_id]
        ):
            raise ValueError("GOODS_STATION_ROLE_AUTHORITY_MISMATCH")
        for owner, kind in (
            (s.bench_owner, "workstation"),
            (s.empty_owner, "workstation"),
            (value.package_pool_owner, "material"),
        ):
            _owner(p, owner, kind)
            if owner in physical:
                raise ValueError("STATION_LOCAL_OWNERS_MUST_BE_DISTINCT")
            physical.add(owner)
        _route(value, c)


def _route(value: GoodsStation, conveyor: ConveyorSource) -> None:
    typed_tuple(value.belt_route, str)
    edges = [conveyor.edges[key] for key in value.belt_route if key in conveyor.edges]
    if not edges or len(edges) != len(value.belt_route):
        raise ValueError("EXPLICIT_KNOWN_STATION_ROUTE_REQUIRED")
    if (
        edges[0].source != conveyor.edges["v3:conv:feed"].source
        or edges[-1].target != conveyor.edges["v3:conv:main-tail"].target
        or any(a.target != b.source for a, b in pairwise(edges))
        or sum(e.target == conveyor.stations[value.station.station_id].work_node_id for e in edges)
        != 1
    ):
        raise ValueError("STATION_ROUTE_MUST_CONNECT_ACTUAL_INTAKE_WORK_OUTPUT")


def _carts(p: CoordinatorProfile, r: UnitResources) -> None:
    if any(type(c.cart) is not FlowCart for c in r.carts):
        raise ValueError("TYPED_CART_REQUIRED")
    if not r.carts or len({c.cart.cart_id for c in r.carts}) != len(r.carts):
        raise ValueError("UNIQUE_PHYSICAL_CARTS_REQUIRED")
    flow = p.world.receipts.flow
    pools: dict[str, str] = {}
    owners: set[str] = set()
    for binding in r.carts:
        c = binding.cart
        if not valid_tick(binding.release_tick):
            raise ValueError("EXPLICIT_CART_RELEASE_DURATION_REQUIRED")
        if type(c) is not FlowCart:
            raise ValueError("TYPED_CART_REQUIRED")
        for key in (c.cart_id, c.owner_id, c.home, c.park):
            text(key)
        if c.home not in flow.graph.node_ids or c.park not in flow.graph.node_ids:
            raise ValueError("UNKNOWN_CART_ANCHOR")
        if any(type(v) is not Fraction or v <= 0 for v in (c.speed_m_s, c.max_gross_kg, c.width_m)):
            raise ValueError("EXACT_POSITIVE_CART_LIMITS_REQUIRED")
        if c.owner_id in owners:
            raise ValueError("CARTS_CANNOT_SHARE_PHYSICAL_OWNER")
        owners.add(c.owner_id)
        _owner(p, c.owner_id, "workstation", exclusive=True)
        _owner(p, binding.carrier_pool_owner, "material")
        if pools.setdefault(binding.carrier_pool_owner, c.home) != c.home:
            raise ValueError("MATERIAL_POOL_CANNOT_TELEPORT_BETWEEN_CART_HOMES")


def _ports(p: CoordinatorProfile, r: UnitResources) -> None:
    if any(type(b.port) is not FlowPort for b in r.ports):
        raise ValueError("TYPED_PARCEL_PORT_REQUIRED")
    if not r.ports or len({p.port.port_id for p in r.ports}) != len(r.ports):
        raise ValueError("UNIQUE_PARCEL_PORTS_REQUIRED")
    for binding in r.ports:
        port = binding.port
        if type(port) is not FlowPort or not valid_tick(port.service_tick) or not port.service_tick:
            raise ValueError("TYPED_POSITIVE_PARCEL_SERVICE_REQUIRED")
        _windows(ReceiptPort(port.port_id, port.node, port.service_tick, port.windows, (), ()))
        text(port.port_id)
        if port.node not in p.world.receipts.flow.graph.node_ids:
            raise ValueError("UNKNOWN_PARCEL_PORT_NODE")
        _owner(p, binding.shipped_owner, "shipped")
        for whole in p.world.ports:
            if whole.port_id == port.port_id and (
                whole.node_id,
                whole.windows,
                whole.shipped_owner,
            ) != (port.node, port.windows, binding.shipped_owner):
                raise ValueError("SHARED_PARCEL_WHOLE_PORT_AUTHORITY_MISMATCH")


def _assignments(p: CoordinatorProfile, r: UnitResources) -> None:
    pickers = {x.actor_id: x for x in r.pickers}
    if len(r.pickers) != 12 or set(pickers) != {f"P{i:02}" for i in range(1, 13)}:
        raise ValueError("ALL_TWELVE_PICKER_BINDINGS_REQUIRED")
    carts = {c.cart.cart_id for c in r.carts}
    for picker in r.pickers:
        typed_tuple(picker.cart_ids, str)
        if len(set(picker.cart_ids)) != len(picker.cart_ids):
            raise ValueError("EXPLICIT_UNIQUE_PICKER_CART_ELIGIBILITY_REQUIRED")
        if not set(picker.cart_ids) <= carts:
            raise ValueError("UNKNOWN_ELIGIBLE_CART")
        _owner(p, "actor:" + picker.actor_id, "worker", exclusive=True)
    orders = p.world.receipts.flow.orders
    if len(r.assignments) != len(orders) or {a.order_id for a in r.assignments} != {
        o.order_id for o in orders
    }:
        raise ValueError("ONE_EXACT_ASSIGNMENT_PER_UNIT_ORDER_REQUIRED")
    for a in r.assignments:
        for value in (a.order_id, a.picker_id, a.cart_id, a.station_id, a.shipper_id, a.port_id):
            text(value)
        if (
            a.picker_id not in pickers
            or a.cart_id not in pickers[a.picker_id].cart_ids
            or a.station_id not in {s.station.station_id for s in r.stations}
            or a.shipper_id not in {"S01", "S02"}
            or a.port_id not in {b.port.port_id for b in r.ports}
        ):
            raise ValueError("UNKNOWN_OR_INELIGIBLE_UNIT_ASSIGNMENT")
    _unique_promises(p)


def _unique_promises(p: CoordinatorProfile) -> None:
    orders = p.world.receipts.flow.orders
    materials = [x for o in orders for x in (o.carrier_id, o.package_id)]
    units = [v.unit_id for o in orders for v in o.carrier_placements]
    if len(set(materials)) != len(materials) or len(set(units)) != len(units):
        raise ValueError("MATERIAL_OR_UNIT_PROMISED_TWICE")


def _owner(p: CoordinatorProfile, key: str, kind: str, *, exclusive: bool = False) -> None:
    text(key)
    owners = {o.owner_id: o for o in p.world.receipts.flow.owners}
    owner = owners.get(key)
    if owner is None or owner.kind != kind or (exclusive and owner.capacity != 1):
        raise ValueError("MISSING_FINITE_UNIT_RESOURCE_OWNER")


def _default_aliases(p: CoordinatorProfile, r: UnitResources) -> None:
    flow = p.world.receipts.flow
    cart = next((c for c in r.carts if c.cart.cart_id == flow.cart.cart_id), None)
    station = next(s for s in r.stations if s.station.station_id == flow.station.station_id)
    port = next((v for v in r.ports if v.port.port_id == flow.port.port_id), None)
    if (
        cart is None
        or cart.cart != flow.cart
        or cart.carrier_pool_owner != flow.carrier_pool_owner
        or station.station != flow.station
        or station.belt_route != flow.belt_route
        or station.package_pool_owner != flow.package_pool_owner
        or port is None
        or port.port != flow.port
        or port.shipped_owner != flow.shipped_owner
    ):
        raise ValueError("DEFAULT_VIEW_MUST_ALIAS_ACTUAL_REGISTERED_RESOURCES")
