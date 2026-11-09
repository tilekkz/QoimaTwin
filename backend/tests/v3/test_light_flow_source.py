"""Real pinned source anchors and stock, with separately declared synthetic materials/services."""

from dataclasses import replace
from fractions import Fraction as F

from app.v3.light_flow_engine import LightFlowEngine
from app.v3.light_flow_models import FlowProfile
from app.v3.light_flow_source import bind_source_profile
from tests.v3.test_belt_runtime import source_bundle, source_catalog
from tests.v3.test_light_flow_fixtures import hand_profile


def source_profile() -> FlowProfile:
    template = hand_profile()
    park, station, ship = "v3:service:CART_PARK", "v3:service:PK06", "v3:service:OUT_S_EXPRESS"
    actors = tuple(
        replace(
            a,
            home=park
            if a.actor_id == "P01"
            else station
            if a.actor_id == "K06"
            else ship
            if a.actor_id == "S01"
            else "v3:service:PK01",
        )
        for a in template.actors
    )
    hu = "v3:HU:initial:DEMO_001:01"
    units = tuple(
        replace(p, unit_id=f"{hu}:unit:{n + 1:04d}")
        for n, p in enumerate(template.orders[0].carrier_placements)
    )
    order = replace(
        template.orders[0], source_hu=hu, carrier_placements=units, package_placements=units
    )
    carrier = template.materials[0]
    carrier = replace(
        carrier,
        recipe=replace(
            carrier.recipe,
            recipe_id="source-small-carrier-v1",
            provenance="ADR0045 declared narrow carrier; no M07 asset resize",
            outer=(F(".32"), F(".24"), F(".24")),
            inner=(F(".30"), F(".22"), F(".22")),
        ),
    )
    template = replace(
        template,
        profile_id="source-light-three-units-v1",
        provenance="ADR0045 explicit logical services; no hand/mesh contact proof",
        actors=actors,
        orders=(order,),
        materials=(carrier, template.materials[1]),
        cart=replace(template.cart, home=park),
    )
    return bind_source_profile(source_bundle(), source_catalog(), template)


def test_source_binding_keeps_real_stock_endpoints_and_port_rule() -> None:
    profile = source_profile()
    assert len(profile.stock.containers) == 530 and len(profile.stock.units) == 12256
    assert profile.orders[0].source_node == "v3:module:SMALL_E:019:B5:worker:node"
    assert profile.orders[0].cart_source_node == "v3:module:SMALL_E:019:B5:cart:node"
    assert profile.cart.park == "v3:service:CART_PARK"
    assert profile.intake_node == "v3:service:CONVEYOR_IN"
    assert profile.output_node == "v3:service:CONVEYOR_OUT"
    assert profile.station.node == "v3:service:PK06"
    assert profile.port.service_tick == 20_000_000
    assert profile.port.windows == ((0, 28_800_000_000),)
    assert profile.source_revision == source_bundle().source_revision


def test_actual_source_three_units_complete_without_claiming_measured_hand_service() -> None:
    result = LightFlowEngine(source_profile(), source_catalog()).run(600_000_000, 1200_000_000)
    assert result.status == "complete"
    assert result.at_end.balance.shipped_units_by_sku == (("DEMO_001", 3),)
    assert result.at_end.balance.gross_mass_kg == F("9404.10")  # original9403.85+.20+.05
    assert result.at_end.balance.shipped_mass_kg == F(".155")
    assert not result.at_end.leases and not result.at_end.belt.leases
    detachment = next(e.tick for e in result.events if e.kind == "source_carrier_detached")
    pickup = next(e.tick for e in result.events if e.kind == "picked")
    assert detachment < pickup
    pick = next(
        e.operation
        for e in result.events
        if e.operation and e.kind == "operation_completed" and e.operation.kind == "pick"
    )
    assert pick.source_node == "v3:module:SMALL_E:019:B5:worker:node"
    assert pick.cart_id is None
