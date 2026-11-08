"""New actor custody never silently broadens the existing material-relocate API."""

import pytest

from app.v3.stock_models import StockError
from tests.v3.test_stock_fixtures import placements
from tests.v3.test_stock_receipt_fixtures import receiving_ledger


def test_old_material_relocate_still_rejects_worker_without_changing_authority() -> None:
    ledger = receiving_ledger()
    before = ledger.inventory_snapshot(), ledger.history
    with pytest.raises(StockError, match="destination owner"):
        ledger.relocate("old", ledger.revision, "C1", "worker")
    assert (ledger.inventory_snapshot(), ledger.history) == before


def test_explicit_material_worker_transfer_uses_one_finite_owner_and_atomic_capacity() -> None:
    ledger = receiving_ledger()
    delta = ledger.transfer_material_to_worker("one", 0, "C1", "worker")
    assert delta.operation == "transfer_material_to_worker"
    assert ledger.contents("C1").container.owner_id == "worker"
    before = ledger.inventory_snapshot(), ledger.history
    with pytest.raises(StockError, match="capacity"):
        ledger.transfer_material_to_worker("two", ledger.revision, "P1", "worker")
    assert (ledger.inventory_snapshot(), ledger.history) == before
    ledger.check_invariants()


def test_explicit_material_transfer_rejects_source_wrapper_and_nonworker_destination() -> None:
    ledger = receiving_ledger()
    before = ledger.inventory_snapshot(), ledger.history
    with pytest.raises(StockError, match="source wrapper"):
        ledger.transfer_material_to_worker("source", 0, "HU1", "worker")
    with pytest.raises(StockError, match="destination owner"):
        ledger.transfer_material_to_worker("workstation", 0, "C1", "work")
    assert (ledger.inventory_snapshot(), ledger.history) == before


def test_new_material_custody_cannot_bypass_exact_unit_claim() -> None:
    ledger = receiving_ledger()
    ledger.pick("pick", 0, "HU1", "C1", placements(1, 2, 3))
    claim = ledger.reserve_units("claim", "job", 1, "C1", ("U1", "U2", "U3"))
    before = ledger.inventory_snapshot(), ledger.history
    with pytest.raises(StockError, match="reserved"):
        ledger.transfer_material_to_worker("unauthorized", 1, "C1", "worker")
    assert (ledger.inventory_snapshot(), ledger.history) == before
    ledger.transfer_material_to_worker("authorized", 1, "C1", "worker", claim_id="claim")
    assert ledger.contents("C1").container.owner_id == "worker" and ledger.claims == (claim,)
    ledger.check_invariants()
