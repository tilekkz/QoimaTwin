"""Conservative module admission includes original stock and every promised receipt."""

from fractions import Fraction as F

from app.v3.relocation_models import RelocationPlace, RelocationProfile
from app.v3.stock_receipts import receipt_recipes
from app.v3.stock_validation import require


def validate_capacity(
    profile: RelocationProfile, source: RelocationPlace, target: RelocationPlace, mass: F
) -> None:
    places = {p.owner_id: p for p in profile.places}
    limits: dict[str, tuple[F, int]] = {}
    for place in profile.places:
        current = (place.module_max_gross_kg, place.module_max_hus)
        require(
            limits.setdefault(place.module_id, current) == current, "Conflicting module capacity"
        )
    stock = profile.coordinator.world.receipts.flow.stock
    require(
        all(c.owner_id in places for c in stock.containers),
        "All original module slot bindings required",
    )
    receipts = profile.coordinator.world.receipts.receipts
    require(
        all(r.slot_owner_id in places for r in receipts),
        "All promised module slot bindings required",
    )
    tokens = {u.unit_id: u for u in stock.units}
    containers = {c.container_id: c for c in stock.containers}
    residents = [(places[c.owner_id].module_id, c.recipe.max_gross_kg) for c in stock.containers]
    for receipt in receipts:
        unit, wrapper = receipt_recipes(receipt.definition.sku_id, tokens, containers)
        future_mass = receipt.definition.quantity_units * unit.gross_mass_kg + wrapper.tare_kg
        residents.append((places[receipt.slot_owner_id].module_id, future_mass))
    if source.module_id != target.module_id:
        residents.append((target.module_id, mass))
    for module in {source.module_id, target.module_id}:
        masses = [value for identity, value in residents if identity == module]
        maximum_mass, maximum_hus = limits[module]
        require(len(masses) <= maximum_hus, "Relocation module HU capacity")
        require(sum(masses, F(0)) <= maximum_mass, "Relocation module payload")
