"""Incremental audits inspect changed SKUs without weakening the full ledger audit."""

from __future__ import annotations

from contextlib import suppress
from typing import Self

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.contracts.loader import ContractBundle
from app.exporter.run import export_run
from app.inventory.ledger import Holding, Ledger, LedgerError, Location, LocKind, ReservationLine
from app.simulation.engine import Engine
from app.simulation.fixtures import fixture_inputs, load_fixture
from app.simulation.invariants import InvariantViolation, check_invariants
from app.storage.canonical_json import canonical_bytes, sha256_hex
from tests.builders import run_inputs, scenario

FACE = Location(LocKind.PICKFACE, "FACE")
TOTE = Location(LocKind.TOTE, "T001")
X = Holding("X", "LX", FACE)


class ObservedUnits(int):
    reads: list[str]
    sku: str

    def __new__(cls, value: int, sku: str, reads: list[str]) -> Self:
        instance = super().__new__(cls, value)
        instance.sku, instance.reads = sku, reads
        return instance

    def __radd__(self, other: int) -> int:
        self.reads.append(self.sku)
        return other + int(self)


def test_settled_check_skips_untouched_sku_quantities(bundle: ContractBundle) -> None:
    engine = Engine(run_inputs(bundle, bundle.directory, scenario([])), check_invariants=True)
    check_invariants(engine)
    ledger = engine.ctx.ledger
    sku_x, sku_y = ledger.skus()[:2]
    observed = next(holding for holding in ledger._balances if holding.sku_id == sku_y)
    reads: list[str] = []
    ledger._balances[observed] = ObservedUnits(ledger._balances[observed], sku_y, reads)
    ledger.accept_receipt(sku_x, "NEW", Location(LocKind.RECEIVING, "R"), 1)
    check_invariants(engine)
    assert reads == []
    assert ledger.check_conservation() == []
    assert reads == [sku_y]  # The public full audit still independently reads every SKU.


@pytest.mark.parametrize("operation", ["initial", "receipt", "reserve", "pick", "release", "move"])
def test_every_public_mutation_marks_affected_sku_and_failed_audit_retries(operation: str) -> None:
    ledger = Ledger()
    ledger.add_initial("X", "LX", FACE, 5)
    if operation in {"pick", "release"}:
        ledger.try_reserve("O", [ReservationLine(X, 1)])
    assert ledger.check_dirty_conservation() == []
    if operation == "initial":
        ledger.add_initial("X", "LX", FACE, 1)
    elif operation == "receipt":
        ledger.accept_receipt("X", "R", TOTE, 1)
    elif operation == "reserve":
        ledger.try_reserve("O", [ReservationLine(X, 1)])
    elif operation == "pick":
        ledger.pick("O", X, 1, TOTE)
    elif operation == "release":
        ledger.release_order("O")
    else:
        ledger.transfer_location(FACE, TOTE)
    holding = next(iter(ledger._balances))
    ledger._balances[holding] += 1
    issues = ledger.check_dirty_conservation()
    assert issues and "units" in issues[0]
    assert ledger.check_dirty_conservation() == issues
    ledger._balances[holding] -= 1
    assert ledger.check_dirty_conservation() == []


def test_initial_audit_detects_direct_corruption() -> None:
    ledger = Ledger()
    ledger.add_initial("X", "LX", FACE, 5)
    ledger._balances[X] += 1
    assert ledger.check_dirty_conservation() == ["X: expected 5 units, found 6"]


def test_explicit_full_audit_detects_corruption_even_without_public_mutation() -> None:
    ledger = Ledger()
    ledger.add_initial("X", "LX", FACE, 5)
    assert ledger.check_dirty_conservation() == []
    ledger._balances[X] += 1
    assert ledger.check_dirty_conservation(full=True) == ["X: expected 5 units, found 6"]


def test_scoped_audit_checks_reservation_and_positive_balance() -> None:
    ledger = Ledger()
    ledger.add_initial("X", "LX", FACE, 5)
    assert ledger.check_dirty_conservation() == []
    ledger.try_reserve("O", [ReservationLine(X, 1)])
    ledger._reserved[X] = 6
    assert any("reserved 6" in issue for issue in ledger.check_dirty_conservation())
    ledger._reserved[X] = 1
    ledger._balances[X] = 0
    assert any("non-positive" in issue for issue in ledger.check_dirty_conservation())


def test_rejected_mutations_do_not_schedule_a_scan() -> None:
    ledger = Ledger()
    ledger.add_initial("X", "LX", FACE, 5)
    assert ledger.check_dirty_conservation() == []
    reads: list[str] = []
    ledger._balances[X] = ObservedUnits(5, "X", reads)
    assert not ledger.try_reserve("O", [ReservationLine(X, 6)])
    with pytest.raises(LedgerError):
        ledger.accept_receipt("X", "R", TOTE, 0)
    ledger.release_order("unknown")
    assert ledger.check_dirty_conservation() == []
    assert reads == []


def test_nonledger_invariants_remain_active_after_clean_stock_audit(bundle: ContractBundle) -> None:
    engine = Engine(run_inputs(bundle, bundle.directory, scenario([])), check_invariants=True)
    check_invariants(engine)
    engine.picking.allocated_totes.add("T001")
    with pytest.raises(InvariantViolation, match="overlap"):
        check_invariants(engine)


@given(st.lists(st.tuples(st.integers(0, 5), st.integers(1, 6)), max_size=50))
@settings(max_examples=80, deadline=None)
def test_changed_audit_matches_full_audit_after_mixed_mutations(
    commands: list[tuple[int, int]],
) -> None:
    ledger = Ledger()
    ledger.add_initial("X", "LX", FACE, 8)
    ledger.add_initial("Y", "LY", FACE, 8)
    for operation, quantity in commands:
        # Also compare after rejected mutations, which must not alter stock or reservations.
        with suppress(LedgerError):
            _command(ledger, operation, quantity)
        assert ledger.check_conservation() == []
        assert ledger.check_dirty_conservation() == []


def _command(ledger: Ledger, operation: int, quantity: int) -> None:
    if operation == 0:
        ledger.add_initial("X", "LX", FACE, quantity)
    elif operation == 1:
        ledger.accept_receipt("Y", "LY", FACE, quantity)
    elif operation == 2:
        ledger.try_reserve("O", [ReservationLine(X, quantity)])
    elif operation == 3:
        ledger.pick("O", X, quantity, TOTE)
    elif operation == 4:
        ledger.release_order("O")
    else:
        ledger.transfer_location(FACE, TOTE)
        ledger.transfer_location(TOTE, FACE)


def test_incremental_audit_preserves_fixture_bytes_and_event_hash(
    bundle: ContractBundle, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = fixture_inputs(bundle, load_fixture(bundle.directory))
    incremental = Engine(inputs, check_invariants=True)
    actual = export_run(incremental, incremental.run(), validate=False)

    def full_audit(ledger: Ledger) -> list[str]:
        return ledger.check_conservation()

    monkeypatch.setattr(Ledger, "check_dirty_conservation", full_audit)
    reference = Engine(inputs, check_invariants=True)
    expected = export_run(reference, reference.run(), validate=False)
    assert canonical_bytes(actual) == canonical_bytes(expected)
    assert sha256_hex(actual["events"]) == sha256_hex(expected["events"])
