"""Receipt deadline is source-specific; post-intake putaway/return may drain."""

from app.v3.receipt_flow_engine import ReceiptFlowEngine
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor, receipt_hand_profile


def test_receipt_at_exact_horizon_is_credited_and_putaway_drains_without_new_pick() -> None:
    result = ReceiptFlowEngine(receipt_hand_profile(), receipt_conveyor()).run(
        12 * SECOND, 50 * SECOND
    )
    assert result.at_horizon.receipts[0].credited_tick == 12 * SECOND
    assert len(result.at_horizon.inventory.locations) == 48
    assert result.at_end.receipts[0].placed_tick == 23 * SECOND
    assert result.at_end.receipts[0].returned_tick == 33 * SECOND
    assert result.at_end.orders[0].admitted_tick is None
    assert result.status == "partial" and not result.at_end.balance.shipped_units_by_sku


def test_receipt_service_crossing_horizon_never_registers_future_stock() -> None:
    result = ReceiptFlowEngine(receipt_hand_profile(), receipt_conveyor()).run(
        12 * SECOND - 1, 50 * SECOND
    )
    assert result.at_end.receipts[0].credited_tick is None
    assert result.at_end.receipts[0].admitted_tick is None
    assert len(result.at_end.inventory.locations) == 24
    assert not result.at_end.inventory.registered_receipts


def test_end_cap_retains_real_receiver_custody_and_future_motion_endpoint() -> None:
    result = ReceiptFlowEngine(receipt_hand_profile(), receipt_conveyor()).run(
        12 * SECOND, 20 * SECOND
    )
    receiver = next(w for w in result.at_end.workers if w.actor_id == "R01")
    assert receiver.operation is not None and receiver.operation.planned_end_tick == 22 * SECOND
    assert receiver.node is None and receiver.paid_ticks == 20 * SECOND
    hu = next(c for c in result.at_end.inventory.containers if c.container_id == "HU2")
    assert hu.owner_id == "actor:R01" and len(result.at_end.inventory.claims) == 1
    assert result.at_end.receipts[0].placed_tick is None
    assert all(event.tick <= 20 * SECOND for event in result.events)


def test_business_shipment_precedes_paid_return_and_repeat_run_is_identical() -> None:
    profile = receipt_hand_profile()
    first = ReceiptFlowEngine(profile, receipt_conveyor()).run(216 * SECOND, 218 * SECOND)
    second = ReceiptFlowEngine(profile, receipt_conveyor()).run(216 * SECOND, 218 * SECOND)
    assert first == second
    assert first.at_horizon.orders[0].shipped_tick == 215_170_000
    assert first.at_horizon.balance.shipped_units_by_sku == (("SKU1", 3),)
    shipper = next(w for w in first.at_end.workers if w.actor_id == "S01")
    assert shipper.operation is not None and shipper.operation.planned_end_tick == 220_170_000
    assert first.status == "partial" and first.at_end.tick == 218 * SECOND
    assert sum(w.paid_ticks for w in first.at_end.workers) == 89_830_000
