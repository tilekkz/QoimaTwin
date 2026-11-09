"""Inventory ledger: conservation, all-or-nothing reservation, transfers (ADR 0005, gates I1-I5)."""

from __future__ import annotations

import pytest

from app.inventory.ledger import (
    Holding,
    Ledger,
    LedgerError,
    Location,
    LocKind,
    ReservationLine,
)

FACE_X = Location(LocKind.PICKFACE, "S_X")
FACE_Y = Location(LocKind.PICKFACE, "S_Y")
TOTE = Location(LocKind.TOTE, "T001")
X = Holding("SKU_X", "LOT_X", FACE_X)
Y = Holding("SKU_Y", "LOT_Y", FACE_Y)


def _ledger(x_units: int = 2, y_units: int = 0) -> Ledger:
    ledger = Ledger()
    ledger.add_initial("SKU_X", "LOT_X", FACE_X, x_units)
    if y_units:
        ledger.add_initial("SKU_Y", "LOT_Y", FACE_Y, y_units)
    return ledger


def test_I1_competing_orders_cannot_overreserve() -> None:
    ledger = _ledger(x_units=2)
    assert ledger.try_reserve("O1", [ReservationLine(X, 2)])
    assert not ledger.try_reserve("O2", [ReservationLine(X, 1)])
    assert ledger.on_hand(X) == 2
    assert ledger.reserved(X) == 2
    assert ledger.check_conservation() == []


def test_I2_reservation_does_not_add_physical_stock() -> None:
    ledger = _ledger(x_units=2)
    ledger.try_reserve("O1", [ReservationLine(X, 2)])
    assert ledger.physical_units("SKU_X") == 2


def test_I3_pick_moves_reserved_units_into_tote() -> None:
    ledger = _ledger(x_units=2)
    ledger.try_reserve("O1", [ReservationLine(X, 2)])
    ledger.pick("O1", X, 2, TOTE)
    assert ledger.on_hand(X) == 0
    assert ledger.reserved(X) == 0
    assert ledger.quantity_at("SKU_X", TOTE) == 2
    assert ledger.physical_units("SKU_X") == 2
    assert ledger.check_conservation() == []


def test_I4_missing_line_rolls_back_whole_reservation() -> None:
    ledger = _ledger(x_units=5)
    missing_y = Holding("SKU_Y", "LOT_Y", FACE_Y)
    assert not ledger.try_reserve("O1", [ReservationLine(X, 2), ReservationLine(missing_y, 1)])
    assert ledger.reserved(X) == 0
    assert ledger.on_hand(X) == 5


def test_I5_initial_plus_receipts_equals_stock_plus_dispatch() -> None:
    ledger = _ledger(x_units=5)
    receiving = Location(LocKind.RECEIVING, "RCV")
    ledger.accept_receipt("SKU_X", "LOT_R1", receiving, 3)
    ledger.try_reserve("O1", [ReservationLine(X, 2)])
    ledger.pick("O1", X, 2, TOTE)
    ledger.transfer_location(TOTE, Location(LocKind.DISPATCHED, "DOCK"))
    buckets = ledger.buckets("SKU_X")
    assert buckets[LocKind.DISPATCHED] == 2
    assert ledger.physical_units("SKU_X") - buckets[LocKind.DISPATCHED] == 6
    assert ledger.check_conservation() == []


def test_pick_more_than_reserved_is_rejected_without_change() -> None:
    ledger = _ledger(x_units=5)
    ledger.try_reserve("O1", [ReservationLine(X, 1)])
    with pytest.raises(LedgerError):
        ledger.pick("O1", X, 2, TOTE)
    assert ledger.on_hand(X) == 5
    assert ledger.reserved(X) == 1


def test_pick_for_other_order_is_rejected() -> None:
    ledger = _ledger(x_units=5)
    ledger.try_reserve("O1", [ReservationLine(X, 1)])
    with pytest.raises(LedgerError):
        ledger.pick("O2", X, 1, TOTE)


def test_duplicate_reservation_lines_are_summed() -> None:
    ledger = _ledger(x_units=3)
    assert not ledger.try_reserve("O1", [ReservationLine(X, 2), ReservationLine(X, 2)])
    assert ledger.try_reserve("O1", [ReservationLine(X, 1), ReservationLine(X, 2)])
    assert ledger.reserved(X) == 3


def test_reserving_twice_for_same_order_is_rejected() -> None:
    ledger = _ledger(x_units=3)
    ledger.try_reserve("O1", [ReservationLine(X, 1)])
    with pytest.raises(LedgerError):
        ledger.try_reserve("O1", [ReservationLine(X, 1)])


def test_transfer_location_moves_everything_and_keeps_lots() -> None:
    ledger = _ledger(x_units=4, y_units=4)
    ledger.try_reserve("O1", [ReservationLine(X, 1), ReservationLine(Y, 2)])
    ledger.pick("O1", X, 1, TOTE)
    ledger.pick("O1", Y, 2, TOTE)
    wip = Location(LocKind.PACK_WIP, "PK01")
    moved = ledger.transfer_location(TOTE, wip)
    assert sorted((h.sku_id, h.lot_id, q) for h, q in moved) == [
        ("SKU_X", "LOT_X", 1),
        ("SKU_Y", "LOT_Y", 2),
    ]
    assert ledger.contents(TOTE) == {}
    assert ledger.contents(wip) == {"SKU_X": 1, "SKU_Y": 2}


def test_negative_or_zero_quantities_are_rejected() -> None:
    ledger = Ledger()
    with pytest.raises(LedgerError):
        ledger.add_initial("SKU_X", "LOT_X", FACE_X, 0)
    with pytest.raises(LedgerError):
        ledger.accept_receipt("SKU_X", "LOT_X", FACE_X, -1)


def test_conservation_detects_tampering() -> None:
    ledger = _ledger(x_units=2)
    ledger._balances[X] = 3  # simulate a bug that creates stock
    assert ledger.check_conservation() == ["SKU_X: expected 2 units, found 3"]


def test_release_order_returns_unpicked_reservation() -> None:
    ledger = _ledger(x_units=4)
    ledger.try_reserve("O1", [ReservationLine(X, 3)])
    ledger.release_order("O1")
    assert ledger.reserved(X) == 0
    assert ledger.try_reserve("O2", [ReservationLine(X, 4)])
