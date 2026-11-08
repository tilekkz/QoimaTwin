"""Retrying an old shipment must not consume a later claim with a reused identity."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.stock_commands import ShipHUCommand
from app.v3.stock_models import Placement, StockError
from tests.v3.test_stock_receipt_fixtures import receipt, receiving_ledger


def test_cached_shipment_retry_preserves_reused_claim_and_rejects_changed_command() -> None:
    state = receiving_ledger()
    state.reserve_hu("claim", "first-job", 0, "HU1")
    command = ShipHUCommand("ship", 0, 100, "HU1", "ship", claim_id="claim")
    result = state.apply_once(command)
    state.receive_hu("receive", 1, receipt(), "worker")
    state.reserve_hu("claim", "next-job", 2, "HU2")
    before, history = state.inventory_snapshot(), state.history
    assert state.apply_once(command) is result
    for changed in (
        replace(command, completed_tick=101),
        replace(command, expected_revision=2),
        replace(command, hu_id="HU2"),
    ):
        with pytest.raises(StockError):
            state.apply_once(changed)
    assert state.inventory_snapshot() == before and state.history == history
    assert state.revision == 2 and before.claim_generation == 3
    assert state.claims[0].container_id == "HU2" and state.claims[0].job_id == "next-job"
    assert state.balance().gross_mass_kg == F("2.13")


def test_whole_claim_cannot_be_used_as_a_legacy_unit_pick_permit() -> None:
    state = receiving_ledger()
    state.reserve_hu("whole", "ship-job", 0, "HU1")
    places = tuple(Placement(f"U{i + 1}", (F(i % 12, 15), F(0), F(i // 12, 20))) for i in range(24))
    before = state.inventory_snapshot()
    with pytest.raises(StockError):
        state.pick("pick", 0, "HU1", "C1", places, claim_id="whole")
    assert state.inventory_snapshot() == before and state.history == ()
    state.transfer_whole_hu("pickup", 0, "HU1", "worker", claim_id="whole")
    after = state.inventory_snapshot()
    with pytest.raises(StockError):
        state.pick("bypass", 1, "HU1", "C1", (places[0],))
    assert state.inventory_snapshot() == after and state.claims == before.claims
