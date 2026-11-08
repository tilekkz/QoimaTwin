"""Paid human routes and explicit synthetic handling stages; no route-anchor jumps."""

from fractions import Fraction

from app.v3.light_flow_models import FlowActor, FlowOrder, FlowProfile
from app.v3.light_flow_state import HumanStep
from app.v3.runtime_graph import RouteRequirements
from app.v3.runtime_time import operation_ticks


def travel(
    profile: FlowProfile,
    actor: FlowActor,
    start: str,
    target: str,
    kind: str,
    carrying: str | None = None,
    *,
    cart: bool = False,
) -> HumanStep:
    margin = profile.path_clearance_m
    if margin is None:
        raise ValueError("Explicit path clearance required")
    width = profile.cart.width_m + 2 * margin if cart else Fraction(0)
    height = None
    if carrying is not None:
        material = next(c for c in profile.materials if c.container_id == carrying)
        width = max(width, material.recipe.outer[0] + 2 * margin)
        height = material.recipe.outer[1] + margin
    required = RouteRequirements(
        mode="manual_cart" if cart else "pedestrian",
        min_clear_width_m=width if width else None,
        min_clear_height_m=height,
    )
    route = profile.graph.shortest_path(start, target, required)
    if route is None:
        raise ValueError("Missing permitted human/cart route")
    speed = min(actor.speed_m_s, profile.cart.speed_m_s) if cart else actor.speed_m_s
    duration = operation_ticks(route.length_m / speed)
    return HumanStep(
        kind, target, duration, route, carrying, profile.cart.cart_id if cart else None
    )


def picker_plan(profile: FlowProfile, actor: FlowActor, order: FlowOrder) -> list[HumanStep]:
    t, c, load = profile.times, profile.cart, order.carrier_id
    cart_source = order.cart_source_node or order.source_node
    return [
        HumanStep("attach", c.home, t.attach, cart_id=c.cart_id),
        travel(profile, actor, c.home, cart_source, "travel_cart", load, cart=True),
        *_source_pick(profile, actor, order),
        travel(profile, actor, cart_source, c.park, "travel_cart", load, cart=True),
        HumanStep("park", c.park, t.park, carrying_id=load, cart_id=c.cart_id),
        HumanStep("detach", c.park, t.detach, carrying_id=load),
        travel(profile, actor, c.park, profile.intake_node, "carry", load),
        HumanStep("deposit", profile.intake_node, t.deposit, carrying_id=load),
        travel(profile, actor, profile.intake_node, c.park, "return"),
        HumanStep("cart_rejoin", c.park, t.attach, cart_id=c.cart_id),
        travel(profile, actor, c.park, c.home, "return", cart=True),
    ]


def _source_pick(profile: FlowProfile, actor: FlowActor, order: FlowOrder) -> list[HumanStep]:
    cart, source, load = profile.cart, order.source_node, order.carrier_id
    pick = HumanStep(
        "pick",
        source,
        profile.times.pick_per_unit * len(order.carrier_placements),
        carrying_id=load,
        cart_id=cart.cart_id if not order.cart_source_node else None,
    )
    if not order.cart_source_node or order.cart_source_node == source:
        return [pick]
    anchor = order.cart_source_node
    return [
        HumanStep("source_park", anchor, profile.times.park, cart_id=cart.cart_id),
        HumanStep("source_detach", anchor, profile.times.detach, carrying_id=load),
        travel(profile, actor, anchor, source, "carry_empty", load),
        pick,
        travel(profile, actor, source, anchor, "carry", load),
        HumanStep(
            "source_attach", anchor, profile.times.attach, carrying_id=load, cart_id=cart.cart_id
        ),
    ]


def shipper_plan(profile: FlowProfile, actor: FlowActor, order: FlowOrder) -> list[HumanStep]:
    return [
        travel(profile, actor, actor.home, profile.output_node, "travel_empty"),
        HumanStep(
            "pickup_package",
            profile.output_node,
            profile.times.pickup,
            carrying_id=order.package_id,
        ),
        travel(profile, actor, profile.output_node, profile.port.node, "carry", order.package_id),
        HumanStep(
            "shipping_service",
            profile.port.node,
            profile.port.service_tick,
            carrying_id=order.package_id,
        ),
        travel(profile, actor, profile.port.node, actor.home, "return"),
    ]
