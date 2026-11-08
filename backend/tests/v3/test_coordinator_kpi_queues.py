"""Queue exposure distinguishes admission, business handover and paid return."""

from dataclasses import replace

from app.v3.coordinator_metrics_queues import queues
from app.v3.light_flow_models import FlowOrderView
from app.v3.receipt_flow_models import ReceiptView
from tests.v3.test_coordinator_kpi_fixtures import S, outcome, point, profile
from tests.v3.test_light_flow_fixtures import hand_orders
from tests.v3.test_receipt_flow_fixtures import receipt_hand_profile


def test_admitted_wip_excludes_pre_admission_queue_and_paid_return() -> None:
    value = profile()
    flow = replace(
        value.world.receipts.flow, orders=(replace(hand_orders(1)[0], arrival_tick=2 * S),)
    )
    value = replace(
        value, world=replace(value.world, receipts=replace(value.world.receipts, flow=flow))
    )
    snapshot = replace(point(value, 10 * S), orders=(FlowOrderView("O1", "picking", 5 * S, None),))
    result = queues(value, outcome(snapshot), snapshot)
    assert result["unit_admitted_business_wip_ticks"] == 5 * S
    assert result["unit_mean_admitted_business_wip"] == {"numerator": 1, "denominator": 2}
    snapshot = replace(
        snapshot, tick=20 * S, orders=(FlowOrderView("O1", "returning", 5 * S, 15 * S),)
    )
    assert queues(value, outcome(snapshot), snapshot)["unit_admitted_business_wip_ticks"] == 10 * S


def test_receipt_wait_and_credited_wip_stop_before_paid_return() -> None:
    value = profile()
    receipts = receipt_hand_profile(arrival_tick=2 * S)
    value = replace(value, world=replace(value.world, receipts=receipts))
    receipt = ReceiptView("R1", "returning", "R01", None, 5 * S, 12 * S, 23 * S, None, None, 20 * S)
    snapshot = replace(point(value, 25 * S), receipts=(receipt,))
    result = queues(value, outcome(snapshot), snapshot)
    assert result["receipt_unadmitted_ticks"] == 3 * S
    assert result["credited_unplaced_hu_ticks"] == 11 * S
    snapshot = replace(
        snapshot,
        tick=20 * S,
        receipts=(
            replace(
                receipt,
                status="carrying",
                placed_tick=None,
            ),
        ),
    )
    assert queues(value, outcome(snapshot), snapshot)["credited_unplaced_hu_ticks"] == 8 * S


def test_future_receipt_is_neither_waiting_nor_credited() -> None:
    value = profile()
    receipts = receipt_hand_profile(arrival_tick=20 * S)
    value = replace(value, world=replace(value.world, receipts=receipts))
    receipt = ReceiptView("R1", "unreleased", None, None, None, None, None, None, None, 0)
    snapshot = replace(point(value, 10 * S), receipts=(receipt,))
    result = queues(value, outcome(snapshot), snapshot)
    assert result["receipt_unadmitted_ticks"] == result["credited_unplaced_hu_ticks"] == 0
