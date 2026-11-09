"""Hand oracles preserve units, individual packaging and the single original wrapper."""

from fractions import Fraction as F

import pytest

from app.v3.stock_models import Placement, StockError
from tests.v3.test_stock_fixtures import ledger, placements


def test_pick_transfer_pack_ship_preserves_mass_and_immutable_ancestry() -> None:
    state = ledger()
    before = state.snapshot()
    delta = state.pick("pick", 0, "HU1", "C1", placements(1, 2, 3))
    assert delta.revision == 1 and delta.unit_ids == ("U1", "U2", "U3")
    assert state.contents("HU1").gross_mass_kg == F(".835")
    assert state.contents("C1").gross_mass_kg == F(".305")
    assert len(before.locations) == 24 and before.revision == 0
    state.transfer("transfer", 1, "C1", "C2", placements(1, 2, 3))
    state.pack("pack", 2, "C2", "P1", placements(1, 2, 3), order_id="ORDER1")
    assert state.contents("P1").gross_mass_kg == F(".155")
    assert state.contents("P1").container.sealed_for == "ORDER1"
    assert {u.token.origin_hu for u in state.contents("P1").units} == {"HU1"}
    state.ship("ship", 3, "P1", "ship")
    balance = state.balance()
    assert balance.units_by_sku == (("SKU1", 24),)
    assert balance.shipped_units_by_sku == (("SKU1", 3),)
    assert balance.onsite_mass_kg == F("1.235")  # .835 + two empty carriers *.20
    assert balance.shipped_mass_kg == F(".155")
    assert balance.gross_mass_kg == F("1.39")  # .94 + .20 + .20 + .05
    assert balance.primary_tare_kg == F(".12") and balance.container_tare_kg == F(".55")
    state.check_invariants()


@pytest.mark.parametrize("failure", ["duplicate", "wrong_source", "unknown", "overlap", "retry"])
def test_failed_pick_is_atomic(failure: str) -> None:
    state = ledger()
    state.pick("first", 0, "HU1", "C1", placements(1))
    before, history = state.snapshot(), state.history
    picks = {
        "duplicate": placements(2, 2),
        "wrong_source": placements(1),
        "unknown": placements(999),
        "overlap": placements(2),
        "retry": placements(3),
    }
    with pytest.raises(StockError):
        state.pick("first" if failure == "retry" else "bad", 1, "HU1", "C1", picks[failure])
    assert state.snapshot() == before and state.history == history


def test_pack_overweight_rolls_back_and_material_is_not_created() -> None:
    state = ledger(parcel_rating=F(".1"))
    state.pick("pick", 0, "HU1", "C1", placements(1, 2, 3))
    before = state.snapshot()
    with pytest.raises(StockError, match="gross"):
        state.pack("bad", 1, "C1", "P1", placements(1, 2, 3), order_id="ORDER1")
    assert state.snapshot() == before and len(state.history) == 1
    with pytest.raises(StockError, match="unknown"):
        state.pack("new", 1, "C1", "invented", placements(1), order_id="ORDER1")
    assert state.snapshot() == before


def test_empty_wrapper_keeps_tare_and_explicit_disposal_never_deletes_mass() -> None:
    state = ledger()
    for index in range(24):
        row, col = divmod(index, 12)
        item = Placement(f"U{index + 1}", (F(col, 15), F(0), F(row, 20)))
        state.pick(f"p{index}", index, "HU1", "C1", (item,))
    assert state.contents("HU1").gross_mass_kg == F(".1")
    state.dispose_empty_wrapper("dispose", 24, "HU1", "waste")
    assert state.balance().disposed_mass_kg == F(".1")
    assert state.balance().gross_mass_kg == F("1.39")
    assert state.contents("HU1").container.owner_id == "waste"


def test_owner_capacity_revision_and_terminal_shipment_are_enforced() -> None:
    state = ledger()
    state.relocate("move", 0, "C1", "single")
    before = state.snapshot()
    with pytest.raises(StockError, match="capacity"):
        state.relocate("other", 1, "C2", "single")
    with pytest.raises(StockError, match="revision"):
        state.pick("stale", 0, "HU1", "C1", placements(1))
    assert state.snapshot() == before
    state.pick("pick", 1, "HU1", "C1", placements(1))
    state.pack("pack", 2, "C1", "P1", placements(1), order_id="O")
    state.ship("ship", 3, "P1", "ship")
    with pytest.raises(StockError, match="terminal"):
        state.ship("again", 4, "P1", "ship")
