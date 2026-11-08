"""Directed paid original-wrapper travel, with source-specific outbound window deadlines."""

from app.v3.light_flow_models import FlowActor
from app.v3.light_flow_state import HumanStep
from app.v3.receipt_flow_models import ReceiptPlace
from app.v3.runtime_graph import RouteRequirements
from app.v3.runtime_time import operation_ticks
from app.v3.stock_models import ContainerRecipe
from app.v3.whole_flow_models import WholeFlowProfile, WholeHUOrder, WholeHUPort


def whole_travel(
    profile: WholeFlowProfile,
    order: WholeHUOrder,
    cargo: ContainerRecipe,
    actor: FlowActor,
    start: str,
    end: str,
    kind: str,
    *,
    loaded: bool,
) -> HumanStep:
    flow = profile.receipts.flow
    margin = flow.path_clearance_m
    if margin is None:
        raise ValueError("Whole-HU route requires explicit clearance")
    requirements = RouteRequirements(
        mode="pedestrian",
        cargo=cargo.allowed_archetypes[0] if loaded else None,
        min_clear_width_m=cargo.outer[0] + 2 * margin if loaded else None,
        min_clear_height_m=cargo.outer[1] + margin if loaded else None,
    )
    route = flow.graph.shortest_path(start, end, requirements)
    if route is None:
        raise ValueError("Missing directed whole-HU route with loaded clearance")
    return HumanStep(
        kind,
        end,
        operation_ticks(route.length_m / actor.speed_m_s),
        route,
        order.hu_id if loaded else None,
    )


def whole_plan(
    profile: WholeFlowProfile,
    order: WholeHUOrder,
    cargo: ContainerRecipe,
    source: ReceiptPlace,
    buffer: ReceiptPlace,
    port: WholeHUPort,
    actor: FlowActor,
) -> list[HumanStep]:
    hu = order.hu_id
    return [
        whole_travel(
            profile, order, cargo, actor, actor.home, source.node_id, "whole_approach", loaded=False
        ),
        HumanStep("whole_pick_slot", source.node_id, profile.pickup_tick, carrying_id=hu),
        whole_travel(
            profile,
            order,
            cargo,
            actor,
            source.node_id,
            buffer.node_id,
            "whole_carry_buffer",
            loaded=True,
        ),
        HumanStep("whole_place_buffer", buffer.node_id, profile.place_tick, carrying_id=hu),
        HumanStep("whole_pick_buffer", buffer.node_id, profile.pickup_tick, carrying_id=hu),
        whole_travel(
            profile,
            order,
            cargo,
            actor,
            buffer.node_id,
            port.node_id,
            "whole_carry_port",
            loaded=True,
        ),
        HumanStep(
            "whole_service",
            port.node_id,
            dict(port.service_ticks)[cargo.allowed_archetypes[0]],
            carrying_id=hu,
        ),
        whole_travel(
            profile, order, cargo, actor, port.node_id, actor.home, "whole_return", loaded=False
        ),
    ]


def outbound_window(port: WholeHUPort, start: int, duration: int) -> bool:
    return any(a <= start < b and start + duration <= b for a, b in port.windows)
