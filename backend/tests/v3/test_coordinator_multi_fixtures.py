"""Six explicit stations and twelve picker bindings on the existing hand world."""

from dataclasses import replace
from fractions import Fraction as F

from app.v3.coordinator_models import CoordinatorProfile
from app.v3.coordinator_units_models import (
    GoodsStation,
    ParcelPort,
    PickerBinding,
    UnitAssignment,
    UnitCart,
    UnitResources,
)
from app.v3.light_flow_models import FlowProfile, FlowStation
from app.v3.runtime_graph import Arc, DirectedGraph
from app.v3.stock_models import StockOwner
from tests.v3.test_belt_runtime import full_route
from tests.v3.test_coordinator_fixtures import staffing_profile
from tests.v3.test_light_flow_fixtures import hand_orders, hand_profile
from tests.v3.test_receipt_flow_fixtures import SECOND


def multi_profile(*, candidate: bool = True, two_carts: bool = False) -> CoordinatorProfile:
    base = staffing_profile()
    flow = _flow(base, two_carts)
    return replace(
        base,
        intents=base.intents if candidate else (),
        unit_resources=_resources(base, flow, two_carts),
        world=replace(base.world, receipts=replace(base.world.receipts, flow=flow)),
    )


def _flow(base: CoordinatorProfile, two_carts: bool) -> FlowProfile:
    material = hand_profile(orders=2)
    flow = base.world.receipts.flow
    capacities = {o.owner_id: o.capacity for o in material.owners}
    owners = tuple(replace(o, capacity=capacities.get(o.owner_id, o.capacity)) for o in flow.owners)
    owners += tuple(o for o in material.owners if o.owner_id not in {x.owner_id for x in owners})
    owners += tuple(StockOwner(f"pool{i:02}", "material", 2) for i in range(1, 6))
    owners += tuple(StockOwner(f"empty{i:02}", "workstation", 2) for i in range(1, 6))
    owners += tuple(StockOwner(f"actor:P{i:02}", "worker", 1) for i in range(2, 13))
    if two_carts:
        owners += (StockOwner("cart02", "workstation", 1),)
    actors = tuple(
        replace(a, home="KH") if a.actor_id in {"K01", "K02", "K03", "K04"} else a
        for a in flow.actors
    )
    return replace(
        flow,
        graph=multi_graph(flow.graph),
        actors=actors,
        owners=owners,
        materials=tuple(
            replace(c, owner_id="pool05") if c.container_id == "P1" else c
            for c in material.materials
        ),
        orders=tuple(replace(o, arrival_tick=80 * SECOND) for o in hand_orders(2)),
    )


def _stations(base: CoordinatorProfile) -> tuple[GoodsStation, ...]:
    return tuple(
        GoodsStation(
            FlowStation(
                s.station_id,
                s.node_id,
                s.bench_owner,
                "empties" if s.station_id == "PK06" else "empty" + s.station_id[-2:],
            ),
            full_route(int(s.station_id[-2:])),
            "K" + s.station_id[-2:],
            "package-pool" if s.station_id == "PK06" else "pool" + s.station_id[-2:],
        )
        for s in base.stations
    )


def _carts(flow: FlowProfile, two_carts: bool) -> tuple[UnitCart, ...]:
    carts: tuple[UnitCart, ...] = (UnitCart(flow.cart, flow.carrier_pool_owner, 0),)
    if two_carts:
        carts += (
            UnitCart(
                replace(flow.cart, cart_id="CART02", owner_id="cart02"), flow.carrier_pool_owner, 0
            ),
        )
    return carts


def _resources(base: CoordinatorProfile, flow: FlowProfile, two_carts: bool) -> UnitResources:
    carts = _carts(flow, two_carts)
    return UnitResources(
        _stations(base),
        carts,
        tuple(
            PickerBinding(f"P{i:02}", tuple(c.cart.cart_id for c in carts)) for i in range(1, 13)
        ),
        (ParcelPort(flow.port, flow.shipped_owner),),
        (
            UnitAssignment("O1", "P01", "CART01", "PK05", "S01", flow.port.port_id),
            UnitAssignment(
                "O2",
                "P02" if two_carts else "P01",
                "CART02" if two_carts else "CART01",
                "PK06",
                "S01",
                flow.port.port_id,
            ),
        ),
    )


def multi_graph(graph: DirectedGraph) -> DirectedGraph:
    arcs = list(graph.arcs)
    for home, station in (("REST05", "ST05"), *(("KH", f"ST{i:02}") for i in range(1, 5))):
        for a, b in ((home, station), (station, home)):
            arcs.append(Arc(f"multi:{a}:{b}", a, b, F(2), F(2), modes=frozenset({"pedestrian"})))
    return DirectedGraph("six-station-hand-v1", graph.node_ids, arcs)
