"""Creation IDs and terminal ancestry stay unique through rejected and successful receipts."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.stock_ledger import StockLedger
from app.v3.stock_models import StockError, StockOwner
from tests.v3.test_stock_fixtures import source_seed_fixture
from tests.v3.test_stock_receipt_fixtures import receipt, receiving_ledger


def test_shipped_hu_identity_is_not_reused_and_failed_new_receipt_id_stays_available() -> None:
    state = receiving_ledger()
    created = state.receive_hu("receive", 0, receipt(), "worker")
    state.ship_whole_hu("ship", 1, "HU2", "ship")
    before, history = state.inventory_snapshot(), state.history
    repeated = receipt(receipt_id="R3", hu_id="HU2", lot_id="LOT3")
    with pytest.raises(StockError):
        state.receive_hu("retry-id", 2, repeated, "worker")
    assert state.inventory_snapshot() == before and state.history == history
    state.receive_hu("retry-id", 2, replace(repeated, hu_id="HU3"), "worker")
    assert state.revision == 3 and len(state.history) == 3
    assert state.balance().units_by_sku == (("SKU1", 72),)
    assert state.balance().onsite_units_by_sku == (("SKU1", 48),)
    assert state.balance().shipped_units_by_sku == (("SKU1", 24),)
    assert state.balance().gross_mass_kg == F("3.07")  # Three*.94 + .20 carrier + .05 parcel.
    shipped = state.contents("HU2")
    assert shipped.container.owner_id == "ship"
    assert all(a is b.token for a, b in zip(created.created_tokens, shipped.units, strict=True))
    assert len(state.inventory_snapshot().registered_receipts) == 2


def test_generated_receipt_unit_id_collision_does_not_replace_existing_ancestry() -> None:
    seed = source_seed_fixture()
    collision = replace(seed.units[0], unit_id="HU2:unit:0001")
    seed = replace(seed, units=(collision, *seed.units[1:]))
    state = StockLedger(seed, owners=(StockOwner("worker", "worker", 1),))
    before = state.inventory_snapshot()
    with pytest.raises(StockError):
        state.receive_hu("receive", 0, receipt(), "worker")
    assert state.inventory_snapshot() == before and state.history == ()
    assert state._tokens[collision.unit_id] is collision
    state.receive_hu("receive", 0, receipt(hu_id="HU3"), "worker")
    assert state._tokens[collision.unit_id] is collision
    assert len(state.snapshot().locations) == 48 and state.revision == 1
    assert state.balance().gross_mass_kg == F("1.88")  # Two source wrappers, no extra materials.
    state.check_invariants()
