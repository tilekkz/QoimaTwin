"""STD receipt20/31/41 followed by a whole-HU handover78/return83, derived before DES."""

from app.v3.whole_flow_engine import WholeFlowEngine
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor
from tests.v3.test_whole_flow_shared_fixtures import standard_receipt_chain


def test_standard_receipt_and_whole_outbound_use_one_registry_and_calendar() -> None:
    result = WholeFlowEngine(standard_receipt_chain(), receipt_conveyor()).run(
        100 * SECOND, 200 * SECOND
    )
    receipt, job = result.at_end.receipts[0], result.at_end.whole_orders[0]
    assert (receipt.credited_tick, receipt.placed_tick, receipt.returned_tick) == (
        20 * SECOND,
        31 * SECOND,
        41 * SECOND,
    )
    assert (job.admitted_tick, job.picked_tick, job.buffered_tick) == (
        31 * SECOND,
        34 * SECOND,
        38 * SECOND,
    )
    assert (job.shipped_tick, job.returned_tick) == (78 * SECOND, 83 * SECOND)
    assert dict(result.at_end.balance.units_by_sku) == {"SKU1": 48}
    assert dict(result.at_end.balance.onsite_units_by_sku) == {"SKU1": 24}
    assert dict(result.at_end.balance.shipped_units_by_sku) == {"SKU1": 24}
    assert not result.at_end.inventory.claims and not result.at_end.leases


def test_receipt_service_exact_horizon_can_put_away_but_cannot_start_outbound_after_h() -> None:
    result = WholeFlowEngine(standard_receipt_chain(), receipt_conveyor()).run(
        20 * SECOND, 100 * SECOND
    )
    assert result.at_horizon.receipts[0].credited_tick == 20 * SECOND
    assert result.at_end.receipts[0].returned_tick == 41 * SECOND
    assert result.at_end.whole_orders[0].admitted_tick is None
    assert result.status == "partial"


def test_standard_service_crossing_horizon_does_not_credit_future_tokens() -> None:
    result = WholeFlowEngine(standard_receipt_chain(), receipt_conveyor()).run(
        20 * SECOND - 1, 100 * SECOND
    )
    assert result.at_end.receipts[0].credited_tick is None
    assert len(result.at_end.stock.locations) == 24
    assert not result.at_end.inventory.registered_receipts
