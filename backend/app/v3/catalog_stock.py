"""Project physical HU ownership and floor poses without introducing new stock."""

from collections import defaultdict
from fractions import Fraction

from app.v3.catalog_geometry import floor_pose
from app.v3.interface import CatalogSource, Json, V3InterfaceError, document, fields


def initial_stock(bundle: CatalogSource) -> Json:
    storage = document(bundle, "storage-slots-v3.json")
    modules = {row["module_id"]: row for row in storage["modules"]}
    slots = {row["slot_id"]: row for row in storage["slots"]}
    archetypes = {
        row["archetype_id"]: row for row in document(bundle, "cargo-catalog-v3.json")["records"]
    }
    skus = {row["sku_id"]: row for row in document(bundle, "sku-catalog-v3.json")["skus"]}
    rows = document(bundle, "baseline-assignment-v3.json")["assignments"]
    units = [_handling_unit(row, modules, slots, archetypes, skus) for row in rows]
    _unique(units, "handling_unit_id")
    _unique(rows, "slot_id")
    totals: dict[str, int] = defaultdict(int)
    for unit in units:
        totals[unit["sku_id"]] += unit["quantity_units"]
    mass = sum(Fraction(str(unit["gross_mass_kg"])) for unit in units)
    return {
        "handling_units": units,
        "inventory_by_sku": [
            {"sku_id": sku, "quantity_units": quantity} for sku, quantity in sorted(totals.items())
        ],
        "totals": {
            "handling_units": len(units),
            "occupied_slots": len(rows),
            "quantity_units": sum(totals.values()),
            "gross_mass_kg": float(mass),
        },
    }


def _handling_unit(row: Json, modules: Json, slots: Json, archetypes: Json, skus: Json) -> Json:
    try:
        slot, module = slots[row["slot_id"]], modules[row["module_id"]]
        archetype, sku = archetypes[row["archetype_id"]], skus[row["sku_id"]]
    except KeyError as exc:
        raise V3InterfaceError(f"unresolved initial stock reference: {exc.args[0]}") from exc
    if slot["module_id"] != row["module_id"] or sku["archetype_id"] != row["archetype_id"]:
        raise V3InterfaceError("initial stock has inconsistent module/archetype binding")
    if slot["reserve_only"] or slot["retrieval_blocked"]:
        raise V3InterfaceError("static baseline cannot silently admit reserve stock")
    hu = archetype["handling_unit"]
    if (
        type(row["quantity_units"]) is not int
        or row["quantity_units"] != hu["units_per_handling_unit"]
    ):
        raise V3InterfaceError("initial HU quantity differs from its frozen full-HU recipe")
    return {
        **fields(row, "handling_unit_id lot_id sku_id archetype_id quantity_units"),
        "owner": {"kind": "storage_slot", "id": row["slot_id"]},
        "pose": _pose(row, module),
        "dimensions_xyz_m": hu["dimensions_xyz_m"],
        "gross_mass_kg": hu["gross_mass_kg"],
        "model_scale_factor": 1,
    }


def _pose(row: Json, module: Json) -> Json:
    if row["orientation_id"] != "upright_xyz":
        raise V3InterfaceError("unsupported initial HU orientation")
    return {
        "world_pos": floor_pose(row["placement"], module),
        "yaw_rad": module["yaw_rad"],
        "origin": "floor_centre_XZ_Y0",
        "orientation_id": row["orientation_id"],
    }


def _unique(rows: list[Json], key: str) -> None:
    values = [row[key] for row in rows]
    if len(values) != len(set(values)):
        raise V3InterfaceError(f"duplicate initial stock {key}")
