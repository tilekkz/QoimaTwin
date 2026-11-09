"""Pure conveyor plans and physical payloads for C publication replay."""

from dataclasses import replace
from fractions import Fraction

from app.v3.belt_models import BeltJob, BeltStep
from app.v3.belt_plan import compile_job
from app.v3.conveyor_models import ConveyorPayload, ConveyorSource
from app.v3.coordinator_run_inventory import InventoryJournal


def payload(inventory: InventoryJournal, key: str, identity: str, kind: str) -> ConveyorPayload:
    contents = inventory.ledger.contents(identity)
    recipe = contents.container.recipe
    return ConveyorPayload(
        identity, kind, recipe.outer, contents.gross_mass_kg, "upright_xyz", key, recipe.provenance
    )


def parcel(inventory: InventoryJournal, key: str) -> ConveyorPayload:
    order = inventory.units[key]
    carrier, package = (
        inventory.ledger.contents(order.carrier_id),
        inventory.ledger.contents(order.package_id),
    )
    recipe = package.container.recipe
    mass = recipe.tare_kg + sum((u.token.recipe.gross_mass_kg for u in carrier.units), Fraction(0))
    return ConveyorPayload(
        order.package_id, "sealed_parcel", recipe.outer, mass, "upright_xyz", key, recipe.provenance
    )


def job(inventory: InventoryJournal, key: str, tick: int) -> BeltJob:
    order, view = inventory.units[key], inventory.views[key]
    return BeltJob(
        key,
        order.carrier_id,
        payload(inventory, key, order.carrier_id, "order_tote"),
        tick,
        view.belt_route,
        view.station.station_id,
        view.times.pack,
    )


def steps(source: ConveyorSource, candidate: BeltJob, clear: int) -> tuple[BeltStep, ...]:
    values = compile_job(source, candidate)
    station = next(i for i, step in enumerate(values) if step.phase == "station")
    return (
        *values[: station + 1],
        replace(values[station], duration_tick=clear),
        *values[station + 1 :],
    )
