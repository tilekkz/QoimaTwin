"""Whole-wrapper and individual-unit promises share the same physical authority."""

from fractions import Fraction as F

import pytest

from app.v3.stock_models import Placement, StockError
from tests.v3.test_stock_fixtures import ledger as legacy_ledger
from tests.v3.test_stock_receipt_fixtures import receiving_ledger


def test_unit_claim_blocks_whole_hu_and_direct_unreserved_pick() -> None:
    state = receiving_ledger()
    state.reserve_units("C", "pick-job", 0, "HU1", ("U1", "U2"))
    with pytest.raises(StockError, match=r"claim|reserved"):
        state.reserve_hu("H", "ship-job", 0, "HU1")
    with pytest.raises(StockError, match=r"claim|reserved"):
        state.transfer_whole_hu("bad", 0, "HU1", "worker")
    with pytest.raises(StockError, match=r"claim|reserved"):
        state.pick("bad", 0, "HU1", "C1", (Placement("U1", (F(0), F(0), F(0))),))
    assert state.revision == 0 and len(state.claims) == 1


def test_disjoint_unit_claims_coexist_and_success_consumes_only_its_claim() -> None:
    state = receiving_ledger()
    state.reserve_units("A", "job-A", 0, "HU1", ("U1",))
    state.reserve_units("B", "job-B", 0, "HU1", ("U2",))
    state.pick("pick", 0, "HU1", "C1", (Placement("U1", (F(0), F(0), F(0))),), claim_id="A")
    assert [claim.claim_id for claim in state.claims] == ["B"]
    with pytest.raises(StockError):
        state.release_claim("B", "job-A")
    state.release_claim("B", "job-B")
    assert not state.claims and state.revision == 1


def test_whole_hu_claim_retains_custody_during_transfer_and_consumes_on_shipment() -> None:
    state = receiving_ledger()
    state.reserve_hu("H", "ship-job", 0, "HU1")
    with pytest.raises(StockError):
        state.reserve_units("U", "pick-job", 0, "HU1", ("U1",))
    state.transfer_whole_hu("pickup", 0, "HU1", "worker", claim_id="H")
    assert len(state.claims) == 1
    state.ship_whole_hu("ship", 1, "HU1", "ship", claim_id="H")
    assert state.inventory_snapshot().claims == () and state.revision == 2


def test_failed_pick_preserves_claim_and_all_stock() -> None:
    state = receiving_ledger()
    state.reserve_units("C", "job", 0, "HU1", ("U1",))
    before, claims = state.snapshot(), state.claims
    with pytest.raises(StockError):
        state.pick("bad", 0, "HU1", "C1", (Placement("U1", (F(5), F(0), F(0))),), claim_id="C")
    assert state.snapshot() == before and state.claims == claims


@pytest.mark.parametrize("operation", ["transfer", "pack", "relocate", "ship"])
def test_all_legacy_material_mutators_obey_existing_unit_claims(operation: str) -> None:
    state = legacy_ledger()
    place = (Placement("U1", (F(0), F(0), F(0))),)
    state.pick("pick", 0, "HU1", "C1", place)
    container = "C1"
    if operation == "ship":
        state.pack("pack", 1, "C1", "P1", place, order_id="O")
        container = "P1"
    state.reserve_units("C", "job", state.revision, container, ("U1",))
    before = state.inventory_snapshot()
    with pytest.raises(StockError, match=r"claim|reserved"):
        if operation == "transfer":
            state.transfer("bad", state.revision, "C1", "C2", place)
        elif operation == "pack":
            state.pack("bad", state.revision, "C1", "P1", place, order_id="O")
        elif operation == "relocate":
            state.relocate("bad", state.revision, "C1", "single")
        else:
            state.ship("bad", state.revision, "P1", "ship")
    assert state.inventory_snapshot() == before


def test_claim_generation_is_separate_and_canonical_snapshot_contains_claims() -> None:
    state = receiving_ledger()
    before = state.inventory_snapshot()
    claim = state.reserve_units("U", "job", 0, "HU1", ("U1",))
    after = state.inventory_snapshot()
    assert after.revision == 0 and after.claim_generation == 1 and after.claims == (claim,)
    assert not before.claims and before.claim_generation == 0
    state.release_claim("U", "job")
    assert state.inventory_snapshot().claim_generation == 2
    assert state.snapshot().containers == before.containers
    assert state.snapshot().locations == before.locations and state.revision == 0
