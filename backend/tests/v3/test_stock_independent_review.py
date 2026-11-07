"""Independent conservation, terminal ownership and typed-state corruption probes."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.stock_ledger import StockLedger
from app.v3.stock_models import Placement, StockError, StockOwner, UnitToken
from tests.v3.test_stock_fixtures import ledger, placements


def all_units() -> tuple[Placement, ...]:
    return tuple(Placement(f"U{n + 1}", (F(n % 12, 15), F(0), F(n // 12, 10))) for n in range(24))


def test_full_pick_keeps_wrapper_and_disposal_preserves_exact_total() -> None:
    state = ledger()
    initial = state.balance()
    delta = state.pick("pick", 0, "HU1", "C1", all_units())
    assert state.contents("HU1").gross_mass_kg == F(".1")
    assert state.contents("C1").gross_mass_kg == F("1.04")
    assert delta.before[0].gross_mass_kg == F(".94")
    state.pack("pack", 1, "C1", "P1", all_units(), order_id="order-1")
    state.ship("ship", 2, "P1", "ship")
    state.dispose_empty_wrapper("dispose", 3, "HU1", "waste")
    balance = state.balance()
    assert balance.gross_mass_kg == initial.gross_mass_kg == F("1.39")
    assert balance.disposed_mass_kg == F(".1") and balance.shipped_mass_kg == F(".89")
    assert balance.onsite_mass_kg == F(".4")
    assert balance.shipped_units_by_sku == (("SKU1", 24),)
    assert len(state.snapshot().containers) == 4
    assert {u.token.origin_hu for u in state.contents("P1").units} == {"HU1"}


@pytest.mark.parametrize("operation", ["wrong_source", "overlap", "off_floor", "capacity"])
def test_failed_moves_preserve_history_revision_locations_and_balance(operation: str) -> None:
    state = ledger(parcel_rating=F(".1"))
    state.pick("pick", 0, "HU1", "C1", placements(1, 2))
    before = (state.snapshot(), state.history, state.balance())
    with pytest.raises(StockError):
        if operation == "wrong_source":
            state.pick("invalid", 1, "HU1", "C2", placements(1))
        elif operation == "overlap":
            duplicate = (Placement("U1", (F(0),) * 3), Placement("U2", (F(0),) * 3))
            state.transfer("invalid", 1, "C1", "C2", duplicate)
        elif operation == "off_floor":
            state.transfer("invalid", 1, "C1", "C2", (Placement("U1", (F(0), F(1, 10), F(0))),))
        else:
            state.pack("invalid", 1, "C1", "P1", placements(1, 2), order_id="order")
    assert (state.snapshot(), state.history, state.balance()) == before
    state.check_invariants()


def test_shipped_package_cannot_reenter_active_inventory() -> None:
    state = ledger()
    state.pick("pick", 0, "HU1", "C1", placements(1))
    state.pack("pack", 1, "C1", "P1", placements(1), order_id="order")
    state.ship("ship", 2, "P1", "ship")
    before = state.snapshot()
    with pytest.raises(StockError, match="terminal"):
        state.relocate("return", 3, "P1", "bench")
    assert state.snapshot() == before


def test_checker_rejects_equal_but_noninteger_ancestry_ordinal() -> None:
    state = ledger()
    tokens: dict[str, UnitToken] = state._tokens
    tokens["U1"] = replace(tokens["U1"], ordinal=True)
    with pytest.raises(StockError):
        state.check_invariants()


def test_checker_rejects_equal_but_noninteger_owner_capacity() -> None:
    state = ledger()
    owners: dict[str, StockOwner] = state._owners
    owners["slot"] = replace(owners["slot"], capacity=True)
    with pytest.raises(StockError):
        state.check_invariants()


def test_changed_container_identity_never_duplicates_materials() -> None:
    state: StockLedger = ledger()
    containers = state._containers
    containers["C1"] = replace(containers["C1"], container_id="C2")
    with pytest.raises(StockError):
        state.check_invariants()
