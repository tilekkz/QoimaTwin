"""Bind exact C02 packed-unit and outer-wrapper recipes without modifying the pinned source."""

import json
from fractions import Fraction
from typing import Any

from .input_models import V3Bundle
from .stock_models import (
    Container,
    ContainerRecipe,
    StockOwner,
    StockSeed,
    UnitRecipe,
    UnitToken,
    Vec3,
)
from .stock_validation import require

CATALOG_PATH = "docs/v3/contract-proposals/cargo-catalog-v3.json"


def number(value: Any) -> Fraction:
    require(type(value) in {int, Fraction}, "exact source number required")
    return Fraction(value)


def dimensions(value: Any) -> Vec3:
    require(isinstance(value, list) and len(value) == 3, "source dimensions required")
    return number(value[0]), number(value[1]), number(value[2])


def recipes(record: dict[str, Any], revision: str) -> tuple[UnitRecipe, ContainerRecipe]:
    unit, hu = record["unit"], record["handling_unit"]
    archetype = str(record["archetype_id"])
    unit_recipe = UnitRecipe(
        archetype,
        dimensions(unit["dimensions_xyz_m"]),
        number(unit["contents_mass_kg"]),
        number(unit["packaging_tare_mass_kg"]),
    )
    require(
        unit_recipe.gross_mass_kg == number(unit["gross_mass_kg"]), "source unit gross mismatch"
    )
    qty, tare = hu["units_per_handling_unit"], number(hu["packaging_tare_mass_kg"])
    require(type(qty) is int and qty > 0, "source unit count")
    require(
        qty * unit_recipe.gross_mass_kg == number(hu["contents_gross_mass_kg"]), "source contents"
    )
    require(
        qty * unit_recipe.gross_mass_kg + tare == number(hu["gross_mass_kg"]), "source HU gross"
    )
    wrapper = ContainerRecipe(
        f"C02:{archetype}",
        f"{revision}:{CATALOG_PATH}",
        "source_wrapper",
        dimensions(hu["dimensions_xyz_m"]),
        None,
        tare,
        number(hu["gross_mass_kg"]),
        qty,
        (archetype,),
        Fraction(0),
    )
    return unit_recipe, wrapper


def source_seed(bundle: V3Bundle) -> StockSeed:
    """All classes are preserved; enabling SMALL unit picks is a separate ledger restriction."""
    require(CATALOG_PATH in bundle.documents, "missing C02 recipe source")
    document = json.loads(bundle.documents[CATALOG_PATH].canonical_bytes, parse_float=Fraction)
    catalog = {
        row["archetype_id"]: recipes(row, bundle.source_revision) for row in document["records"]
    }
    require(len(catalog) == len(document["records"]), "duplicate source archetype")
    units: list[UnitToken] = []
    containers: list[Container] = []
    for hu in sorted(bundle.handling_units, key=lambda item: item.handling_unit_id):
        require(hu.archetype_id in catalog, "unknown source archetype")
        unit_recipe, wrapper_recipe = catalog[hu.archetype_id]
        require(hu.quantity_units == wrapper_recipe.max_units, "source HU recipe quantity")
        require(
            Fraction(str(hu.gross_mass_kg)) == wrapper_recipe.max_gross_kg, "source typed HU gross"
        )
        require(hu.orientation_id == "upright_xyz", "unsupported source orientation")
        containers.append(Container(hu.handling_unit_id, wrapper_recipe, hu.slot_id))
        for ordinal in range(1, hu.quantity_units + 1):
            units.append(
                UnitToken(
                    f"{hu.handling_unit_id}:unit:{ordinal:04d}",
                    hu.handling_unit_id,
                    hu.sku_id,
                    hu.lot_id,
                    ordinal,
                    unit_recipe,
                )
            )
    owners = tuple(StockOwner(slot.slot_id, "slot", 1) for slot in bundle.slots)
    return StockSeed(tuple(units), tuple(containers), owners)
