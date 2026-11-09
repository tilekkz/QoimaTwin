"""Source binding and pure shared-ledger admission; no engine or worker state exists here."""

from dataclasses import replace
from typing import Any

from app.v3.conveyor_models import ConveyorSource
from app.v3.coordinator_models import CoordinatorProfile, RoleIntent, RoleStation
from app.v3.coordinator_profile_choices import legacy_choices
from app.v3.coordinator_profile_resources import resources
from app.v3.coordinator_units import order_views, preflight_units
from app.v3.coordinator_units_validate import validate_resources
from app.v3.coordinator_validation import validate_horizon, validate_profile
from app.v3.input_models import V3Bundle
from app.v3.light_flow_models import FlowProfile
from app.v3.staff_registry import compile_staff_registry
from app.v3.stock_ledger import StockLedger
from app.v3.whole_flow_validate import _validate_whole_flow
from app.v3.whole_profile_io_decode import decode
from app.v3.whole_profile_source import _bind


def bind(
    bundle: V3Bundle,
    conveyor: ConveyorSource,
    value: dict[str, Any],
) -> tuple[CoordinatorProfile, dict[str, Any], StockLedger]:
    choices = legacy_choices(value)
    world, buffers = decode(bundle, conveyor, choices)
    world, graph_document = _bind(bundle, conveyor, world, buffers)
    registry = compile_staff_registry(value["registry"])
    bound = resources(bundle, conveyor, value, registry)
    flow = world.receipts.flow
    actors = {a.actor_id: a for a in flow.actors}
    intents = tuple(
        RoleIntent(**row, restore_node=actors[row["actor_id"]].home)
        for row in value["role_intents"]
    )
    profile = CoordinatorProfile(
        value["profile_id"],
        value["provenance"],
        world,
        registry,
        tuple(
            RoleStation(s.station.station_id, s.station.node, s.station.bench_owner)
            for s in bound.stations
        ),
        intents,
        bound,
    )
    # Preserve one default view of the same declared objects, not copied physical state.
    cart = next(c.cart for c in bound.carts if c.cart.cart_id == choices["cart"]["cart_id"])
    flow = replace(flow, cart=cart)
    profile = replace(profile, world=replace(world, receipts=replace(world.receipts, flow=flow)))
    return profile, graph_document, validate_bound(profile, conveyor, value)


def validate_bound(
    profile: CoordinatorProfile,
    conveyor: ConveyorSource,
    value: dict[str, Any],
) -> StockLedger:
    validate_profile(profile)
    validate_resources(profile, conveyor)
    validate_horizon(profile, value["horizon_tick"], value["end_tick"])
    views = order_views(profile)

    def units(flow: FlowProfile, source: ConveyorSource, ledger: StockLedger) -> None:
        preflight_units(views, source, ledger)

    return _validate_whole_flow(
        profile.world, conveyor, unit_validator=units, picker_home_at_cart=False
    )
