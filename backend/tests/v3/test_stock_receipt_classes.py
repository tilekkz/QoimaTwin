"""Eight C02 mass recipes with hand geometry: accounting, never heavy-motion admission."""

from fractions import Fraction as F

import pytest

from app.v3.stock_ledger import StockLedger
from app.v3.stock_models import (
    Container,
    ContainerRecipe,
    StockError,
    StockOwner,
    StockSeed,
    UnitRecipe,
    UnitToken,
)
from app.v3.stock_receipts import ReceiptDefinition

ROWS = (
    ("SMALL_CARTON", 24, ".03", ".005", ".10", ".94"),
    ("STANDARD_CARTON", 24, ".20", ".05", ".35", "6.35"),
    ("HEAVY_BOX", 8, "22", "1", "16", "200"),
    ("PALLET_LOAD", 24, "17.2", ".8", "23", "455"),
    ("IBC", 1, "600", "14", "40", "654"),
    ("LONG_BUNDLE", 24, "7.8", ".2", "8", "200"),
    ("DRUM", 1, "160", "12", "8", "180"),
    ("FRAGILE_CRATE", 1, "68", "5", "15", "88"),
)


def eight_class_ledger() -> StockLedger:
    tokens: list[UnitToken] = []
    containers: list[Container] = []
    owners: list[StockOwner] = []
    for archetype, count, contents, primary, tare, gross in ROWS:
        unit = UnitRecipe(archetype, (F(1), F(1), F(1)), F(contents), F(primary))
        wrapper = ContainerRecipe(
            archetype,
            "hand dimensions; C02 mass oracle",
            "source_wrapper",
            (F(2), F(2), F(2)),
            None,
            F(tare),
            F(gross),
            count,
            (archetype,),
            F(0),
        )
        hu = "old:" + archetype
        containers.append(Container(hu, wrapper, "slot:" + archetype))
        owners.extend(
            (StockOwner("slot:" + archetype, "slot", 1), StockOwner("free:" + archetype, "slot", 1))
        )
        tokens.extend(
            UnitToken(f"{hu}:{i}", hu, archetype, "lot:" + archetype, i, unit)
            for i in range(1, count + 1)
        )
    return StockLedger(
        StockSeed(tuple(tokens), tuple(containers), tuple(owners)),
        owners=(StockOwner("buffer", "buffer", 8), StockOwner("shipped", "shipped", 8)),
    )


def test_all_eight_receipts_and_intact_shipments_keep_107_units_and_1784_29_kg() -> None:
    state = eight_class_ledger()
    initial = state.balance()
    assert sum(quantity for _, quantity in initial.units_by_sku) == 107
    assert initial.contents_mass_kg == F("1609.52")
    assert initial.primary_tare_kg == F("64.32")
    assert initial.container_tare_kg == F("110.45")
    assert initial.gross_mass_kg == F("1784.29")
    for archetype, count, *_ in ROWS:
        new = "new:" + archetype
        definition = ReceiptDefinition(
            "R:" + archetype, new, archetype, "lot:new:" + archetype, count
        )
        state.receive_hu("receive:" + archetype, state.revision, definition, "buffer")
        state.transfer_whole_hu("place:" + archetype, state.revision, new, "free:" + archetype)
    assert len(state.snapshot().locations) == 214 and len(state.snapshot().containers) == 16
    assert state.balance().gross_mass_kg == F("3568.58")
    for archetype, *_ in ROWS:
        state.ship_whole_hu("ship:" + archetype, state.revision, "old:" + archetype, "shipped")
    balance = state.balance()
    assert sum(quantity for _, quantity in balance.onsite_units_by_sku) == 107
    assert sum(quantity for _, quantity in balance.shipped_units_by_sku) == 107
    assert balance.onsite_mass_kg == balance.shipped_mass_kg == F("1784.29")
    assert len(state.snapshot().locations) == 214 and len(state.snapshot().containers) == 16
    assert len(state.inventory_snapshot().registered_receipts) == 8
    state.check_invariants()


def test_lot_can_span_same_sku_hus_but_cannot_change_recipe_or_sku() -> None:
    state = eight_class_ledger()
    first = ReceiptDefinition("R1", "HUnew1", "SMALL_CARTON", "shared-lot", 24)
    second = ReceiptDefinition("R2", "HUnew2", "SMALL_CARTON", "shared-lot", 24)
    state.receive_hu("one", 0, first, "buffer")
    state.receive_hu("two", 1, second, "buffer")
    invalid = ReceiptDefinition("R3", "HUnew3", "STANDARD_CARTON", "shared-lot", 24)
    before = state.inventory_snapshot()
    with pytest.raises(StockError, match="lot"):
        state.receive_hu("bad", 2, invalid, "buffer")
    assert state.inventory_snapshot() == before
