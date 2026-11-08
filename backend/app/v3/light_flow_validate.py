"""Fail-closed explicit input validation for the bounded SMALL workflow."""

from dataclasses import fields
from fractions import Fraction

from app.v3.belt_models import BeltJob
from app.v3.belt_plan import compile_job, valid_tick
from app.v3.conveyor_models import ConveyorPayload, ConveyorSource
from app.v3.execution_types import ACTOR_IDS
from app.v3.light_flow_inputs import handoff_inputs
from app.v3.light_flow_models import FlowProfile
from app.v3.light_flow_plan import picker_plan, shipper_plan, travel
from app.v3.stock_ledger import StockLedger


def validate(profile: FlowProfile, conveyor: ConveyorSource) -> StockLedger:
    if not profile.profile_id or not profile.provenance:
        raise ValueError("Explicit versioned synthetic process provenance required")
    actors = {a.actor_id: a for a in profile.actors}
    if set(actors) != set(ACTOR_IDS) or len(profile.actors) != 24:
        raise ValueError("All24 unique source actor identities required")
    if (profile.picker_id, profile.packer_id, profile.shipper_id) != ("P01", "K06", "S01"):
        raise ValueError("Initial bounded slice explicitly activates P01/K06/S01")
    for actor in actors.values():
        if actor.home not in profile.graph.node_ids or not valid_tick(actor.available_tick):
            raise ValueError("Unknown home or invalid actor availability")
        if any(type(v) is not Fraction or v <= 0 for v in (actor.speed_m_s, actor.max_gross_kg)):
            raise ValueError("Explicit exact positive actor capacity/speed required")
    for item in fields(profile.times):
        value = getattr(profile.times, item.name)
        if not valid_tick(value) or value == 0:
            raise ValueError("Explicit positive handling durations required")
    if profile.station.station_id not in conveyor.stations:
        raise ValueError("Unknown source station")
    if any(
        type(v) is not Fraction or v <= 0
        for v in (
            profile.cart.speed_m_s,
            profile.cart.max_gross_kg,
            profile.cart.width_m,
        )
    ):
        raise ValueError("Explicit exact positive cart capacity/speed/width required")
    ledger = StockLedger(profile.stock, owners=profile.owners, materials=profile.materials)
    handoff_inputs(profile, conveyor)
    _orders(profile, conveyor, ledger)
    return StockLedger(profile.stock, owners=profile.owners, materials=profile.materials)


def _orders(profile: FlowProfile, conveyor: ConveyorSource, ledger: StockLedger) -> None:
    order_ids, material_ids, unit_ids = set[str](), set[str](), set[str]()
    actors = {a.actor_id: a for a in profile.actors}
    for order in profile.orders:
        if order.order_id in order_ids or not valid_tick(order.arrival_tick):
            raise ValueError("Duplicate order or invalid arrival")
        order_ids.add(order.order_id)
        units = tuple(p.unit_id for p in order.carrier_placements)
        if not units or set(units) != {p.unit_id for p in order.package_placements}:
            raise ValueError("Picking and packaging must name exactly the same units")
        if unit_ids.intersection(units) or len(units) != len(set(units)):
            raise ValueError("A source unit cannot be promised to two orders")
        unit_ids.update(units)
        for identity in (order.carrier_id, order.package_id):
            if identity in material_ids:
                raise ValueError("Carrier reuse requires an explicit paid return process")
            material_ids.add(identity)
        carrier, package = ledger.contents(order.carrier_id), ledger.contents(order.package_id)
        if (
            carrier.container.owner_id != profile.carrier_pool_owner
            or package.container.owner_id != profile.package_pool_owner
        ):
            raise ValueError("Materials must begin in their declared physical pools")
        ledger.pick(
            order.order_id + ":preflight-pick",
            len(ledger.history),
            order.source_hu,
            order.carrier_id,
            order.carrier_placements,
        )
        _material_capacity(profile, order.order_id, order.carrier_id, units, ledger, conveyor)
        ledger.pack(
            order.order_id + ":preflight-pack",
            len(ledger.history),
            order.carrier_id,
            order.package_id,
            order.package_placements,
            order_id=order.order_id,
        )
        _parcel_capacity(profile, order.order_id, order.package_id, ledger, conveyor)
        picker_plan(profile, actors[profile.picker_id], order)
        shipper_plan(profile, actors[profile.shipper_id], order)
    packer = actors[profile.packer_id]
    travel(profile, packer, packer.home, profile.station.node, "travel_empty")
    travel(profile, packer, profile.station.node, packer.home, "return")


def _parcel_capacity(
    profile: FlowProfile,
    order_id: str,
    package_id: str,
    ledger: StockLedger,
    conveyor: ConveyorSource,
) -> None:
    parcel = ledger.contents(package_id)
    actors = {a.actor_id: a for a in profile.actors}
    if parcel.gross_mass_kg > min(
        actors[profile.shipper_id].max_gross_kg, actors[profile.packer_id].max_gross_kg
    ):
        raise ValueError("Complete parcel including tare exceeds handler capacity")
    payload = ConveyorPayload(
        package_id,
        "sealed_parcel",
        parcel.container.recipe.outer,
        parcel.gross_mass_kg,
        "upright_xyz",
        order_id,
        parcel.container.recipe.provenance,
    )
    station_node = conveyor.stations[profile.station.station_id].work_node_id
    index = next(
        i
        for i, edge_id in enumerate(profile.belt_route)
        if conveyor.edges[edge_id].target == station_node
    )
    compile_job(
        conveyor,
        BeltJob(order_id, package_id, payload, 0, profile.belt_route[index + 1 :], None, 0),
    )


def _material_capacity(
    profile: FlowProfile,
    order_id: str,
    carrier_id: str,
    units: tuple[str, ...],
    ledger: StockLedger,
    conveyor: ConveyorSource,
) -> None:
    carrier = ledger.contents(carrier_id).container
    tokens = {unit.unit_id: unit for unit in profile.stock.units}
    if any(identity not in tokens for identity in units):
        raise ValueError("Unknown original unit")
    gross = carrier.recipe.tare_kg + sum(
        (tokens[key].recipe.gross_mass_kg for key in units), Fraction(0)
    )
    actors = {a.actor_id: a for a in profile.actors}
    if gross > min(profile.cart.max_gross_kg, actors[profile.picker_id].max_gross_kg):
        raise ValueError("Complete carrier including tare exceeds picker/cart capacity")
    if carrier.recipe.tare_kg > actors[profile.packer_id].max_gross_kg:
        raise ValueError("Empty carrier tare exceeds packer capacity")
    payload = ConveyorPayload(
        carrier_id,
        "order_tote",
        carrier.recipe.outer,
        gross,
        "upright_xyz",
        order_id,
        carrier.recipe.provenance,
    )
    compile_job(
        conveyor,
        BeltJob(
            order_id,
            carrier_id,
            payload,
            0,
            profile.belt_route,
            profile.station.station_id,
            profile.times.pack,
        ),
    )
