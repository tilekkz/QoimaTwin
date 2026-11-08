"""Retries are explicit protocol behavior; legacy direct commands remain strict."""

from dataclasses import replace
from fractions import Fraction as F
from typing import cast

import pytest

from app.v3.stock_commands import ReceiveHUCommand, ShipHUCommand, TransferHUCommand
from app.v3.stock_models import StockError
from tests.v3.test_stock_receipt_fixtures import receipt, receiving_ledger


def test_identical_retry_after_later_commit_returns_original_without_effects() -> None:
    state = receiving_ledger()
    command = ReceiveHUCommand("R", 0, 12_000_000, receipt(), "worker")
    result = state.apply_once(command)
    state.apply_once(TransferHUCommand("M", 1, 23_000_000, "HU2", "slot2"))
    before = state.snapshot()
    assert state.apply_once(command) is result
    assert state.snapshot() == before and len(state.history) == 2
    with pytest.raises(StockError, match="duplicate"):
        state.receive_hu("R", 2, receipt(hu_id="HU3", receipt_id="R3"), "worker")


def test_different_retry_and_numeric_equal_wrong_type_cannot_hit_cached_result() -> None:
    state = receiving_ledger()
    command = ReceiveHUCommand("R", 0, 1, receipt(), "worker")
    state.apply_once(command)
    for changed in (
        replace(command, owner_id="buffer"),
        replace(command, expected_revision=1),
        replace(command, completed_tick=cast(int, True)),
        replace(command, completed_tick=cast(int, F(1))),
    ):
        with pytest.raises(StockError):
            state.apply_once(changed)
    assert state.revision == 1


def test_failed_command_does_not_consume_identity_or_advance_revision() -> None:
    state = receiving_ledger()
    bad = ReceiveHUCommand("R", 0, 12, receipt(), "missing")
    with pytest.raises(StockError):
        state.apply_once(bad)
    result = state.apply_once(replace(bad, owner_id="worker"))
    assert result.revision == 1 and len(state.history) == 1


def test_capacity_failure_after_candidate_creation_keeps_all_authorities_and_retry_cache() -> None:
    state = receiving_ledger()
    state.receive_hu("first", 0, receipt(), "buffer")
    state.reserve_hu("claim", "putaway", 1, "HU2")
    command = ReceiveHUCommand("R3", 1, 15, receipt(receipt_id="R3", hu_id="HU3"), "buffer")
    before, history = state.inventory_snapshot(), state.history
    with pytest.raises(StockError, match="capacity"):
        state.apply_once(command)
    assert state.inventory_snapshot() == before and state.history == history
    assert "R3" not in state._applied and "HU3" not in state._registered_containers
    state.transfer_whole_hu("place", 1, "HU2", "slot2", claim_id="claim")
    assert state.apply_once(replace(command, expected_revision=2)).revision == 3
    assert len(state.inventory_snapshot().registered_receipts) == 2


def test_retry_after_unrelated_claim_change_does_not_consume_the_new_claim() -> None:
    state = receiving_ledger()
    command = ReceiveHUCommand("R", 0, 12, receipt(), "worker")
    result = state.apply_once(command)
    state.reserve_hu("claim", "future", 1, "HU2")
    before = state.inventory_snapshot()
    assert state.apply_once(command) is result
    assert state.inventory_snapshot() == before


def test_shipment_retry_does_not_duplicate_departure_or_release_another_claim() -> None:
    state = receiving_ledger()
    state.reserve_hu("S", "outbound", 0, "HU1")
    command = ShipHUCommand("ship", 0, 30_000_000, "HU1", "ship", "S")
    result = state.apply_once(command)
    state.receive_hu("receive", 1, receipt(), "worker")
    state.reserve_hu("R", "putaway", 2, "HU2")
    before = state.inventory_snapshot()
    assert state.apply_once(command) is result
    assert state.inventory_snapshot() == before and len(state.history) == 2
    assert state.balance().shipped_units_by_sku == (("SKU1", 24),)
