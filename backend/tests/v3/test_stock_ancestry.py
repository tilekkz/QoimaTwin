"""Joining physical unit picks retains each original HU wrapper exactly once."""

from dataclasses import replace
from fractions import Fraction as F

from app.v3.stock_ledger import StockLedger
from app.v3.stock_models import Container, Placement, StockOwner
from tests.v3.test_stock_fixtures import placements, recipe, source_seed_fixture


def test_two_source_hus_join_package_without_copying_tare_or_losing_lot_ancestry() -> None:
    seed = source_seed_fixture()
    second_units = tuple(
        replace(u, unit_id=f"V{u.ordinal}", origin_hu="HU2", lot_id="LOT2") for u in seed.units
    )
    seed = replace(
        seed,
        units=seed.units + second_units,
        containers=(
            *seed.containers,
            replace(seed.containers[0], container_id="HU2", owner_id="slot2"),
        ),
        owners=(*seed.owners, StockOwner("slot2", "slot", 1)),
    )
    state = StockLedger(
        seed,
        owners=(StockOwner("bench", "workstation", 2), StockOwner("ship", "shipped", 1)),
        materials=(Container("C", recipe(), "bench"), Container("P", recipe("package"), "bench")),
    )
    state.pick("one", 0, "HU1", "C", placements(1, 2, 3))
    extra = (Placement("V1", (F(".2"), F(0), F(0))), Placement("V2", (F(".27"), F(0), F(0))))
    state.pick("two", 1, "HU2", "C", extra)
    state.pack("pack", 2, "C", "P", placements(1, 2, 3) + extra, order_id="O")
    contents = state.contents("P")
    assert contents.gross_mass_kg == F(".225")  # five*.035 + new .05, no source HU tare
    assert {(u.token.origin_hu, u.token.lot_id) for u in contents.units} == {
        ("HU1", "LOT1"),
        ("HU2", "LOT2"),
    }
    assert state.contents("HU1").gross_mass_kg == F(".835")
    assert state.contents("HU2").gross_mass_kg == F(".87")
    state.ship("ship", 3, "P", "ship")
    assert state.balance().units_by_sku == (("SKU1", 48),)
    assert state.balance().onsite_units_by_sku == (("SKU1", 43),)
    assert state.balance().shipped_units_by_sku == (("SKU1", 5),)
    assert state.balance().gross_mass_kg == F("2.13")  # 2*.94 + .20 + .05
    assert state.balance().container_tare_kg == F(".45")
    assert state.history[0].after[1].gross_mass_kg == F(".305")  # delta remained frozen
