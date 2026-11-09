"""Hand arithmetic: credit12, putaway23, pick29, intake36, returns33/43 seconds."""

from fractions import Fraction as F

from app.v3.receipt_flow_engine import ReceiptFlowEngine
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor, receipt_hand_profile


def test_one_clock_receipt_feeds_three_unit_flow_without_cloning_initial_stock() -> None:
    engine = ReceiptFlowEngine(receipt_hand_profile(), receipt_conveyor())
    before = engine.ledger.inventory_snapshot()
    assert len(before.locations) == 24 and not before.registered_receipts
    result = engine.run(300 * SECOND, 400 * SECOND)
    receipt = result.at_end.receipts[0]
    assert (receipt.credited_tick, receipt.placed_tick, receipt.returned_tick) == (
        12 * SECOND,
        23 * SECOND,
        33 * SECOND,
    )
    times = {e.kind: e.tick for e in result.events if e.order_id == "O1"}
    assert times["picked"] == 29 * SECOND and times["intake_handoff"] == 36 * SECOND
    picker_returns = [
        e.tick
        for e in result.events
        if e.kind == "operation_completed"
        and e.actor_id == "P01"
        and e.operation is not None
        and e.operation.kind == "return"
    ]
    assert picker_returns[-1] == 43 * SECOND
    assert result.status == "complete" and len(result.at_end.workers) == 24
    assert times["shipped"] == 215_170_000  # unchanged belt/human oracle shifted by admission23s
    assert result.at_end.tick == 220_170_000
    assert sum(worker.paid_ticks for worker in result.at_end.workers) == 92 * SECOND
    assert result.at_end.balance.units_by_sku == (("SKU1", 48),)
    assert result.at_end.balance.shipped_units_by_sku == (("SKU1", 3),)
    assert result.at_end.balance.gross_mass_kg == F("2.13")
    assert result.at_end.balance.onsite_mass_kg == F("1.975")
    assert engine.ledger.contents("HU2").gross_mass_kg == F(".835")
    assert engine.ledger.contents("HU1").container is next(
        c for c in before.containers if c.container_id == "HU1"
    )
    assert not result.at_end.inventory.claims and not result.at_end.leases
    assert [e.seq for e in result.events] == list(range(len(result.events)))
