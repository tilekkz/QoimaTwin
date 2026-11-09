"""Receipt credit creates ancestry once, then physical custody preserves the same HU."""

from dataclasses import replace
from fractions import Fraction as F
from typing import cast

import pytest

from app.v3.stock_models import Placement, StockError, UnitLocation
from app.v3.stock_receipts import ReceiptDelta
from tests.v3.test_stock_receipt_fixtures import receipt, received_three, receiving_ledger


def test_receipt_then_three_unit_parcel_uses_one_ancestry_registry() -> None:
    state = receiving_ledger()
    initial = state.snapshot()
    delta = state.receive_hu("receive", 0, receipt(), "worker")
    assert isinstance(delta, ReceiptDelta) and not delta.before
    assert len(delta.created_tokens) == 24 and delta.receipt == receipt()
    assert state.revision == 1 and len(state.snapshot().locations) == 48
    assert state.contents("HU2").container.owner_id == "worker"
    state.transfer_whole_hu("putaway", 1, "HU2", "slot2")
    places = tuple(Placement(key, position) for key, position in received_three())
    state.pick("pick", 2, "HU2", "C1", places)
    state.pack("pack", 3, "C1", "P1", places, order_id="O")
    state.ship("ship", 4, "P1", "ship")
    balance = state.balance()
    assert balance.units_by_sku == (("SKU1", 48),)
    assert balance.onsite_units_by_sku == (("SKU1", 45),)
    assert balance.shipped_units_by_sku == (("SKU1", 3),)
    assert balance.gross_mass_kg == F("2.13")  # .94 + .94 + .20 + .05
    assert balance.shipped_mass_kg == F(".155")
    assert state.contents("HU2").gross_mass_kg == F(".835")
    assert state.contents("HU1").container is initial.containers[1]
    assert {u.token.origin_hu for u in state.contents("P1").units} == {"HU2"}
    state.check_invariants()


@pytest.mark.parametrize("failure", ["duplicate_hu", "duplicate_receipt", "sku", "count", "full"])
def test_receipt_rejection_changes_neither_registry_revision_nor_history(failure: str) -> None:
    state = receiving_ledger()
    state.receive_hu("first", 0, receipt(), "buffer")
    incoming = {
        "duplicate_hu": receipt(receipt_id="R3"),
        "duplicate_receipt": receipt(hu_id="HU3"),
        "sku": receipt(receipt_id="R3", hu_id="HU3", sku_id="unknown"),
        "count": receipt(receipt_id="R3", hu_id="HU3", quantity_units=23),
        "full": receipt(receipt_id="R3", hu_id="HU3"),
    }[failure]
    before, history = state.snapshot(), state.history
    with pytest.raises(StockError):
        state.receive_hu("bad", 1, incoming, "buffer")
    assert state.snapshot() == before and state.history == history and state.revision == 1


@pytest.mark.parametrize("quantity", [True, F(24), 24.0])
def test_receipt_quantity_requires_exact_integer(quantity: object) -> None:
    state = receiving_ledger()
    with pytest.raises(StockError):
        state.receive_hu("bad", 0, receipt(quantity_units=cast(int, quantity)), "worker")
    assert state.revision == 0 and len(state.snapshot().locations) == 24


def test_receipt_cannot_appear_directly_in_a_remote_slot() -> None:
    state = receiving_ledger()
    with pytest.raises(StockError, match=r"owner|custody"):
        state.receive_hu("bad", 0, receipt(), "slot2")
    assert state.revision == 0


def test_intact_whole_hu_moves_and_ships_without_splitting_or_repacking() -> None:
    state = receiving_ledger()
    tokens = tuple(u.token for u in state.contents("HU1").units)
    state.transfer_whole_hu("pickup", 0, "HU1", "worker")
    state.transfer_whole_hu("stage", 1, "HU1", "buffer")
    state.ship_whole_hu("depart", 2, "HU1", "ship")
    assert tuple(u.token for u in state.contents("HU1").units) == tokens
    assert all(a is b.token for a, b in zip(tokens, state.contents("HU1").units, strict=True))
    assert state.contents("HU1").container.sealed_for is None
    assert state.balance().shipped_mass_kg == F(".94")
    with pytest.raises(StockError, match="terminal"):
        state.transfer_whole_hu("return", 3, "HU1", "slot")


def test_partial_wrapper_cannot_fulfil_an_intact_whole_hu_demand() -> None:
    state = receiving_ledger()
    state.pick("unit", 0, "HU1", "C1", (Placement("U1", (F(0), F(0), F(0))),))
    before = state.snapshot()
    with pytest.raises(StockError, match=r"intact|whole"):
        state.ship_whole_hu("bad", 1, "HU1", "ship")
    assert state.snapshot() == before


def test_registered_receipt_ancestry_and_authorized_owner_cannot_be_mutated() -> None:
    state = receiving_ledger()
    state.receive_hu("receive", 0, receipt(), "worker")
    token = state._tokens["HU2:unit:0001"]
    state._tokens[token.unit_id] = replace(token, ordinal=cast(int, F(1)))
    with pytest.raises(StockError, match="ancestry"):
        state.check_invariants()
    state._tokens[token.unit_id] = token
    state._containers["HU2"] = replace(state._containers["HU2"], owner_id="slot2")
    with pytest.raises(StockError, match=r"admission|unauthorized|immutable"):
        state.check_invariants()


def test_untracked_valid_unit_move_is_not_an_authorized_transaction() -> None:
    state = receiving_ledger()
    state._locations["U1"] = UnitLocation("U1", "C1", (F(0), F(0), F(0)))
    with pytest.raises(StockError, match=r"unauthorized|immutable"):
        state.check_invariants()


@pytest.mark.parametrize("kind", ["valid_location", "numeric_equal_recipe"])
def test_committed_whole_hu_state_has_object_authority_after_real_movement(kind: str) -> None:
    state = receiving_ledger()
    state.transfer_whole_hu("pickup", 0, "HU1", "worker")
    container = state._containers["HU1"]
    changed = replace(container, owner_id="slot2")
    if kind == "numeric_equal_recipe":
        changed = replace(container, recipe=replace(container.recipe, max_units=cast(int, F(24))))
    state._containers["HU1"] = changed
    with pytest.raises(StockError):
        state.check_invariants()
