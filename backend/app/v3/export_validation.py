"""Cross-reference and conservation checks remain necessary after valid JSON hashes."""

from collections import defaultdict
from fractions import Fraction

from app.v3.catalog_geometry import hu_bounds
from app.v3.interface import Json, V3InterfaceError


def validate_relations(value: Json) -> None:
    catalog, state = value["catalog"], value["initial_state"]
    names = {
        "skus": ("skus", "sku_id"),
        "archetypes": ("cargo_archetypes", "archetype_id"),
        "slots": ("storage_slots", "slot_id"),
        "modules": ("storage_modules", "module_id"),
        "ports": ("ports", "port_id"),
        "actors": ("actors", "actor_id"),
    }
    indexes = {name: _index(catalog[section], key) for name, (section, key) in names.items()}
    for name, index in indexes.items():
        if catalog["counts"][name] != len(index):
            raise V3InterfaceError(f"catalog count mismatch: {name}")
    _catalog_links(catalog, indexes)
    units = state["handling_units"]
    _index(units, "handling_unit_id")
    owners = [unit["owner"]["id"] for unit in units]
    if len(owners) != len(set(owners)):
        raise V3InterfaceError("initial stock has duplicate slot owners")
    if catalog["counts"]["handling_units"] != len(units):
        raise V3InterfaceError("catalog handling-unit count mismatch")
    for unit in units:
        _unit_links(unit, indexes)
    _totals(state)


def _index(rows: list[Json], key: str) -> Json:
    result = {row[key]: row for row in rows}
    if len(result) != len(rows):
        raise V3InterfaceError(f"duplicate catalog/stock identity: {key}")
    return result


def _require(index: Json, key: str) -> Json:
    if key not in index:
        raise V3InterfaceError(f"unknown catalog reference: {key}")
    result: Json = index[key]
    return result


def _catalog_links(catalog: Json, indexes: Json) -> None:
    for sku in indexes["skus"].values():
        _require(indexes["archetypes"], sku["archetype_id"])
    for slot in indexes["slots"].values():
        _require(indexes["modules"], slot["module_id"])
    for port in indexes["ports"].values():
        for archetype in port["allowed_cargo_archetype_ids"]:
            _require(indexes["archetypes"], archetype)
    for pool in catalog["resource_policy"]["actor_pools"]:
        for actor in pool["actor_ids"]:
            _require(indexes["actors"], actor)
    for pair in catalog["resource_policy"]["equipment_pairs"]:
        _require(indexes["actors"], pair["actor_id"])


def _unit_links(unit: Json, indexes: Json) -> None:
    sku = _require(indexes["skus"], unit["sku_id"])
    archetype = _require(indexes["archetypes"], unit["archetype_id"])
    slot = _require(indexes["slots"], unit["owner"]["id"])
    module = _require(indexes["modules"], slot["module_id"])
    if sku["archetype_id"] != unit["archetype_id"]:
        raise V3InterfaceError("initial HU SKU/archetype mismatch")
    if slot["reserve_only"] or slot["retrieval_blocked"]:
        raise V3InterfaceError("initial HU uses blocked reserve")
    expected = archetype["handling_unit"]
    for name, key in (
        ("quantity_units", "units_per_handling_unit"),
        ("gross_mass_kg", "gross_mass_kg"),
        ("dimensions_xyz_m", "dimensions_xyz_m"),
    ):
        if unit[name] != expected[key]:
            raise V3InterfaceError(f"initial HU differs from archetype: {name}")
    _pose(unit, slot, module)


def _pose(unit: Json, slot: Json, module: Json) -> None:
    pose = unit["pose"]
    if pose["yaw_rad"] != module["yaw_rad"]:
        raise V3InterfaceError("initial HU yaw differs from its owning module")
    lower, upper = hu_bounds(unit)
    bounds = slot["usable_bounds_world"]
    if lower[1] != Fraction(str(bounds["min"][1])):
        raise V3InterfaceError("initial HU does not rest on its slot support")
    for axis in range(3):
        if lower[axis] < Fraction(str(bounds["min"][axis])):
            raise V3InterfaceError("initial HU pose exceeds usable slot bounds")
        if upper[axis] > Fraction(str(bounds["max"][axis])):
            raise V3InterfaceError("initial HU pose exceeds usable slot bounds")


def _totals(state: Json) -> None:
    quantities: dict[str, int] = defaultdict(int)
    lot_skus: dict[str, str] = {}
    mass = Fraction(0)
    for unit in state["handling_units"]:
        quantities[unit["sku_id"]] += unit["quantity_units"]
        mass += Fraction(str(unit["gross_mass_kg"]))
        previous = lot_skus.setdefault(unit["lot_id"], unit["sku_id"])
        if previous != unit["sku_id"]:
            raise V3InterfaceError("initial lot refers to multiple SKUs")
    expected_inventory = [
        {"sku_id": sku, "quantity_units": quantity} for sku, quantity in sorted(quantities.items())
    ]
    expected = {
        "handling_units": len(state["handling_units"]),
        "occupied_slots": len(state["handling_units"]),
        "quantity_units": sum(quantities.values()),
        "gross_mass_kg": float(mass),
    }
    if state["inventory_by_sku"] != expected_inventory or state["totals"] != expected:
        raise V3InterfaceError("initial stock inventory/totals mismatch")
