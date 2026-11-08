"""Paid directed manual receipt legs; source service excludes these travel/handling costs."""

from app.v3.light_flow_models import FlowActor
from app.v3.light_flow_state import HumanStep
from app.v3.receipt_flow_models import ReceiptFlowProfile, ReceiptOffer, ReceiptPlace, ReceiptPort
from app.v3.runtime_graph import RouteRequirements
from app.v3.runtime_time import operation_ticks
from app.v3.stock_models import ContainerRecipe
from app.v3.stock_receipts import receipt_recipes


def wrapper_recipe(profile: ReceiptFlowProfile, offer: ReceiptOffer) -> ContainerRecipe:
    return receipt_recipes(
        offer.definition.sku_id,
        {u.unit_id: u for u in profile.flow.stock.units},
        {c.container_id: c for c in profile.flow.stock.containers},
    )[1]


def receipt_travel(
    profile: ReceiptFlowProfile,
    offer: ReceiptOffer,
    actor: FlowActor,
    start: str,
    target: str,
    kind: str,
    *,
    loaded: bool,
) -> HumanStep:
    margin = profile.flow.path_clearance_m
    if margin is None:
        raise ValueError("Receipt route requires explicit path clearance")
    cargo = wrapper_recipe(profile, offer)
    requirements = RouteRequirements(
        mode="pedestrian",
        cargo="SMALL_CARTON" if loaded else None,
        min_clear_width_m=cargo.outer[0] + 2 * margin if loaded else None,
        min_clear_height_m=cargo.outer[1] + margin if loaded else None,
    )
    route = profile.flow.graph.shortest_path(start, target, requirements)
    if route is None:
        raise ValueError("Missing directed receipt route with loaded clearance")
    return HumanStep(
        kind,
        target,
        operation_ticks(route.length_m / actor.speed_m_s),
        route,
        offer.definition.hu_id if loaded else None,
    )


def receipt_plan(
    profile: ReceiptFlowProfile,
    offer: ReceiptOffer,
    port: ReceiptPort,
    buffer: ReceiptPlace,
    actor: FlowActor,
) -> list[HumanStep]:
    slot = next(p for p in profile.places if p.owner_id == offer.slot_owner_id)
    hu = offer.definition.hu_id
    return [
        receipt_travel(
            profile, offer, actor, actor.home, port.node_id, "receipt_approach", loaded=False
        ),
        HumanStep("receipt_service", port.node_id, port.service_tick),
        receipt_travel(
            profile, offer, actor, port.node_id, buffer.node_id, "receipt_carry_buffer", loaded=True
        ),
        HumanStep("receipt_place_buffer", buffer.node_id, profile.place_tick, carrying_id=hu),
        HumanStep("receipt_pick_buffer", buffer.node_id, profile.pickup_tick, carrying_id=hu),
        receipt_travel(
            profile, offer, actor, buffer.node_id, slot.node_id, "receipt_carry_slot", loaded=True
        ),
        HumanStep("receipt_place_slot", slot.node_id, profile.place_tick, carrying_id=hu),
        receipt_travel(
            profile, offer, actor, slot.node_id, actor.home, "receipt_return", loaded=False
        ),
    ]


def receipt_window(port: ReceiptPort, start: int, duration: int, horizon: int) -> bool:
    return any(
        a <= start < min(b, horizon) and start + duration <= min(b, horizon)
        for a, b in port.windows
    )


def window_wake(port: ReceiptPort, now: int, approach: int, horizon: int) -> int | None:
    options = [
        start - approach
        for start, end in port.windows
        if start - approach > now and start + port.service_tick <= min(end, horizon)
    ]
    return min(options, default=None)
