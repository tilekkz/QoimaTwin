"""Exact bulk views follow committed stock, receipts and mixed unit recipes."""

from fractions import Fraction as F

import pytest

from app.v3.stock_commands import ReceiveHUCommand, TransferHUCommand
from app.v3.stock_models import StockError
from tests.v3.test_stock_fixtures import ledger, placements
from tests.v3.test_stock_mass_independent_retained import _integer_recipe_ledger
from tests.v3.test_stock_mass_independent_transactions import _mixed_claimed
from tests.v3.test_stock_receipt_fixtures import receipt, receiving_ledger


def test_all_containers_include_empty_tare_and_detached_results() -> None:
    state = ledger()
    result = state.gross_masses()
    assert result == {"HU1": F(".94"), "C1": F(".2"), "C2": F(".2"), "P1": F(".05")}
    assert result == {
        c.container_id: state.contents(c.container_id).gross_mass_kg
        for c in state.snapshot().containers
    }
    result["HU1"] = F(999)
    assert state.gross_masses()["HU1"] == F(".94")


def test_pick_pack_ship_and_rejected_commands_keep_fresh_exact_masses() -> None:
    state = ledger()
    state.pick("pick", 0, "HU1", "C1", placements(1, 2))
    assert state.gross_masses() == {"HU1": F(".87"), "C1": F(".27"), "C2": F(".2"), "P1": F(".05")}
    before = state.inventory_snapshot(), state.gross_masses(), state.history
    with pytest.raises(StockError):
        state.pack("bad", 1, "C1", "P1", placements(3), order_id="order")
    assert (state.inventory_snapshot(), state.gross_masses(), state.history) == before
    state.pack("pack", 1, "C1", "P1", placements(1, 2), order_id="order")
    state.ship("ship", 2, "P1", "ship")
    assert state.gross_masses()["C1"] == F(".2")
    assert state.gross_masses()["P1"] == F(".12")
    assert state.gross_masses() == {
        c.container_id: state.contents(c.container_id).gross_mass_kg
        for c in state.snapshot().containers
    }


def test_mixed_recipes_recompute_mass_after_packing() -> None:
    state, items = _mixed_claimed(F(".71"))
    assert state.gross_masses() == {"A": F(".1"), "B": F(".1"), "C": F(".86"), "P": F(".05")}
    state.pack("pack", 2, "C", "P", items, order_id="order", claim_id="pack-claim")
    assert state.gross_masses() == {"A": F(".1"), "B": F(".1"), "C": F(".2"), "P": F(".71")}


def test_receipt_whole_transfer_and_idempotent_retries_do_not_duplicate_mass() -> None:
    state = receiving_ledger()
    command = ReceiveHUCommand("receive", 0, 0, receipt(), "worker")
    first = state.apply_once(command)
    assert state.gross_masses()["HU2"] == F(".94")
    assert state.apply_once(command) is first
    transfer = TransferHUCommand("transfer", 1, 1, "HU2", "slot2")
    moved = state.apply_once(transfer)
    assert state.apply_once(transfer) is moved
    assert state.revision == 2
    assert state.gross_masses() == {"HU1": F(".94"), "HU2": F(".94"), "C1": F(".2"), "P1": F(".05")}


@pytest.mark.parametrize("alias", [True, 1, 1.0])
def test_each_call_revalidates_same_recipe_identity(alias: object) -> None:
    state = _integer_recipe_ledger()
    recipe = state.contents("HU1").units[0].token.recipe
    assert state.gross_masses()["HU1"] == F("24.1")
    object.__setattr__(recipe, "contents_mass_kg", alias)
    with pytest.raises(StockError, match="exact Fraction"):
        state.gross_masses()


@pytest.mark.parametrize("alias", [True, 1, 1.0])
def test_empty_wrapper_tare_cannot_be_a_numeric_alias(alias: object) -> None:
    state = ledger()
    recipe = state.contents("C1").container.recipe
    object.__setattr__(recipe, "tare_kg", F(1))
    assert state.gross_masses()["C1"] == F(1)
    object.__setattr__(recipe, "tare_kg", alias)
    with pytest.raises(StockError, match="exact Fraction"):
        state.gross_masses()
