"""Outbound service may drain after H; future service starts still pay the approach."""

from dataclasses import replace

from app.v3.whole_flow_engine import WholeFlowEngine
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor
from tests.v3.test_whole_flow_fixtures import whole_hand_profile


def test_future_outbound_window_wakes_before_paid_buffer_pickup_and_approach() -> None:
    profile = whole_hand_profile()
    profile = replace(
        profile, ports=(replace(profile.ports[0], windows=((100 * SECOND, 135 * SECOND),)),)
    )
    result = WholeFlowEngine(profile, receipt_conveyor()).run(20 * SECOND, 150 * SECOND)
    job = result.at_end.whole_orders[0]
    assert (job.port_reserved_tick, job.service_started_tick) == (95 * SECOND, 100 * SECOND)
    assert (job.shipped_tick, job.returned_tick) == (135 * SECOND, 140 * SECOND)
    assert job.paid_exposure_ticks == 140 * SECOND
    assert job.port_service_ticks == 35 * SECOND


def test_exact_outbound_window_close_is_inclusive_but_one_tick_short_remains_partial() -> None:
    profile = whole_hand_profile()
    good = replace(profile, ports=(replace(profile.ports[0], windows=((0, 47 * SECOND),)),))
    bad = replace(profile, ports=(replace(profile.ports[0], windows=((0, 47 * SECOND - 1),)),))
    complete = WholeFlowEngine(good, receipt_conveyor()).run(20 * SECOND, 60 * SECOND)
    partial = WholeFlowEngine(bad, receipt_conveyor()).run(20 * SECOND, 60 * SECOND)
    assert complete.status == "complete" and complete.at_end.tick == 52 * SECOND
    assert partial.status == "partial" and partial.at_end.whole_orders[0].shipped_tick is None
    assert partial.at_end.whole_orders[0].buffer_picked_tick is None
