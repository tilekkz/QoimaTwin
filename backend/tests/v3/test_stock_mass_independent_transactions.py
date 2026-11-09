"""Black-box mass boundaries, claims and shipment buckets on explicit hand stock."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.stock_ledger import StockLedger
from app.v3.stock_models import Container, Placement, StockError, StockOwner, StockSeed, UnitToken
from tests.v3.test_stock_fixtures import placements, recipe, source_seed_fixture
from tests.v3.test_stock_receipt_fixtures import receipt, receiving_ledger


def _mixed_seed() -> StockSeed:
    base = source_seed_fixture()
    tokens: list[UnitToken] = []
    containers: list[Container] = []
    owners: list[StockOwner] = []
    for index, name in enumerate(("A", "B"), start=1):
        unit = replace(
            base.units[0].recipe,
            dimensions=(F(index, 10), F(".1"), F(".1")),
            contents_mass_kg=F(index, 10),
            primary_tare_kg=F(index, 100),
        )
        wrapper = replace(
            base.containers[0].recipe,
            recipe_id=f"source:{name}",
            max_units=2,
            max_gross_kg=F(".1") + 2 * F(11 * index, 100),
        )
        tokens.extend(UnitToken(f"{name}{n}", name, name, name, n, unit) for n in (1, 2))
        containers.append(Container(name, wrapper, f"slot:{name}"))
        owners.append(StockOwner(f"slot:{name}", "slot", 1))
    return StockSeed(tuple(tokens), tuple(containers), tuple(owners))


def _mixed_claimed(rating: F) -> tuple[StockLedger, tuple[Placement, ...]]:
    state = StockLedger(
        _mixed_seed(),
        owners=(StockOwner("bench", "workstation", 2), StockOwner("ship", "shipped", 2)),
        materials=(
            Container("C", recipe(), "bench"),
            Container("P", recipe("package", rating=rating), "bench"),
        ),
    )
    items = tuple(
        Placement(identity, (F(x), F(0), F(0)))
        for identity, x in (("A1", "0"), ("A2", ".1"), ("B1", ".2"), ("B2", ".4"))
    )
    state.pick("A", 0, "A", "C", items[:2])
    state.pick("B", 1, "B", "C", items[2:])
    state.reserve_units("pack-claim", "order", 2, "C", tuple(p.unit_id for p in items))
    return state, items


@pytest.mark.parametrize("shortfall", [F(0), F(1, 10**12)])
def test_mixed_same_class_mass_at_exact_limit_preserves_claims_on_failure(shortfall: F) -> None:
    state, items = _mixed_claimed(F(".71") - shortfall)
    assert state.contents("C").gross_mass_kg == F(".86")  # .20 + 2*.11 + 2*.22
    before = (state.inventory_snapshot(), state.history, state.balance())
    if shortfall:
        with pytest.raises(StockError, match="gross capacity"):
            state.pack("pack", 2, "C", "P", items, order_id="order", claim_id="pack-claim")
        assert (state.inventory_snapshot(), state.history, state.balance()) == before
    else:
        state.pack("pack", 2, "C", "P", items, order_id="order", claim_id="pack-claim")
        assert state.contents("P").gross_mass_kg == F(".71") and not state.claims
        state.ship("ship", 3, "P", "ship")
        assert state.balance().onsite_mass_kg == F(".4")
        assert state.balance().shipped_mass_kg == F(".71")
    balance = state.balance()
    assert balance.contents_mass_kg == F(".6") and balance.primary_tare_kg == F(".06")
    assert balance.gross_mass_kg == F("1.11")
    assert balance.units_by_sku == (("A", 2), ("B", 2))
    state.check_invariants()


def test_new_receipt_and_original_units_keep_separate_physical_mass_buckets() -> None:
    state = receiving_ledger()
    state.check_invariants()
    assert state.balance().gross_mass_kg == F("1.19")
    state.receive_hu("receive", 0, receipt(), "worker")
    state.reserve_hu("whole", "whole-order", 1, "HU2")
    state.ship_whole_hu("whole-ship", 1, "HU2", "ship", claim_id="whole")
    state.pick("pick", 2, "HU1", "C1", placements(1, 2, 3))
    state.pack("pack", 3, "C1", "P1", placements(1, 2, 3), order_id="parcel")
    state.ship("parcel-ship", 4, "P1", "ship")
    balance = state.balance()
    assert balance.units_by_sku == (("SKU1", 48),)
    assert balance.onsite_units_by_sku == (("SKU1", 21),)
    assert balance.shipped_units_by_sku == (("SKU1", 27),)
    assert balance.contents_mass_kg == F("1.44") and balance.primary_tare_kg == F(".24")
    assert balance.container_tare_kg == F(".45")
    assert balance.onsite_mass_kg == F("1.035") and balance.shipped_mass_kg == F("1.095")
    assert balance.gross_mass_kg == F("2.13") and not state.claims
    assert len(state.inventory_snapshot().registered_receipts) == 1
    state.check_invariants()
