"""Exact service deadlines allow approach before a window and putaway afterwards."""

from dataclasses import replace

from app.v3.receipt_flow_engine import ReceiptFlowEngine
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor, receipt_hand_profile


def test_future_window_wakes_before_opening_to_pay_approach() -> None:
    profile = receipt_hand_profile()
    port = replace(profile.ports[0], windows=((5 * SECOND, 15 * SECOND),))
    profile = replace(profile, ports=(port,), flow=replace(profile.flow, orders=()))
    result = ReceiptFlowEngine(profile, receipt_conveyor()).run(20 * SECOND, 50 * SECOND)
    receipt = result.at_end.receipts[0]
    assert (
        receipt.admitted_tick,
        receipt.credited_tick,
        receipt.placed_tick,
        receipt.returned_tick,
    ) == (3 * SECOND, 15 * SECOND, 26 * SECOND, 36 * SECOND)
    assert result.status == "complete"


def test_declared_home_at_service_point_pays_zero_approach_without_teleport() -> None:
    profile = receipt_hand_profile()
    actors = tuple(
        replace(a, home="RECEIVE") if a.actor_id == "R01" else a for a in profile.flow.actors
    )
    profile = replace(profile, flow=replace(profile.flow, actors=actors, orders=()))
    result = ReceiptFlowEngine(profile, receipt_conveyor()).run(10 * SECOND, 40 * SECOND)
    receipt = result.at_end.receipts[0]
    assert (receipt.credited_tick, receipt.placed_tick, receipt.returned_tick) == (
        10 * SECOND,
        21 * SECOND,
        29 * SECOND,
    )
    assert result.at_horizon.receipts[0].credited_tick == 10 * SECOND
    assert result.status == "complete"


def test_arrival_at_horizon_remains_outside_warehouse_registry() -> None:
    profile = receipt_hand_profile(arrival_tick=12 * SECOND)
    result = ReceiptFlowEngine(profile, receipt_conveyor()).run(12 * SECOND, 50 * SECOND)
    assert result.at_end.receipts[0].status == "unreleased"
    assert result.at_end.receipts[0].admitted_tick is None
    assert len(result.at_end.inventory.locations) == 24
    assert not result.at_end.inventory.registered_receipts
