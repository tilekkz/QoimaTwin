"""Immutable per-order views, never a mutable swap of the common physical profile."""

from dataclasses import replace

from app.v3.conveyor_models import ConveyorSource
from app.v3.coordinator_models import CoordinatorProfile
from app.v3.coordinator_units_models import UnitResources
from app.v3.light_flow_inputs import _handoff_inputs
from app.v3.light_flow_models import FlowProfile
from app.v3.light_flow_plan import picker_plan, travel
from app.v3.light_flow_state import HumanStep
from app.v3.light_flow_validate import _orders
from app.v3.stock_ledger import StockLedger


def order_views(profile: CoordinatorProfile) -> dict[str, FlowProfile]:
    flow, resources = profile.world.receipts.flow, profile.unit_resources
    if resources is None:
        return {}
    return {a.order_id: order_view(flow, resources, a.order_id) for a in resources.assignments}


def order_view(flow: FlowProfile, resources: UnitResources, order_id: str) -> FlowProfile:
    assignment = next(a for a in resources.assignments if a.order_id == order_id)
    station = next(s for s in resources.stations if s.station.station_id == assignment.station_id)
    cart = next(c for c in resources.carts if c.cart.cart_id == assignment.cart_id)
    port = next(p for p in resources.ports if p.port.port_id == assignment.port_id)
    order = next(o for o in flow.orders if o.order_id == order_id)
    return replace(
        flow,
        picker_id=assignment.picker_id,
        packer_id=station.primary_id,
        shipper_id=assignment.shipper_id,
        cart=cart.cart,
        station=station.station,
        port=port.port,
        shipped_owner=port.shipped_owner,
        belt_route=station.belt_route,
        carrier_pool_owner=cart.carrier_pool_owner,
        package_pool_owner=station.package_pool_owner,
        orders=(order,),
    )


def preflight_units(
    views: dict[str, FlowProfile],
    conveyor: ConveyorSource,
    ledger: StockLedger,
) -> None:
    # One prospective ledger for every order, including future declared receipt contents.
    for _, view in sorted(views.items()):
        _handoff_inputs(view, conveyor, "worker", picker_home_at_cart=False)
        _orders(view, conveyor, ledger)
        picking_steps(view)


def picking_steps(profile: FlowProfile, release_tick: int = 0) -> list[HumanStep]:
    actor = next(a for a in profile.actors if a.actor_id == profile.picker_id)
    core = picker_plan(profile, actor, profile.orders[0])
    if release_tick:
        core.append(
            HumanStep("cart_release", profile.cart.home, release_tick, cart_id=profile.cart.cart_id)
        )
    if actor.home == profile.cart.home:
        return core
    return [
        travel(profile, actor, actor.home, profile.cart.home, "cart_approach"),
        *core,
        travel(profile, actor, profile.cart.home, actor.home, "picker_return"),
    ]
