"""Before implementation: one bay gives SMALL37/42 then STANDARD77/82, not72/77."""

from dataclasses import replace

from app.v3.whole_flow_engine import WholeFlowEngine
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor
from tests.v3.test_whole_flow_shared_fixtures import two_whole_jobs


def test_two_workers_share_one_conservatively_reserved_port() -> None:
    result = WholeFlowEngine(two_whole_jobs(), receipt_conveyor()).run(100 * SECOND, 200 * SECOND)
    first, second = result.at_end.whole_orders
    assert (first.actor_id, second.actor_id) == ("S01", "S02")
    assert (first.shipped_tick, first.returned_tick) == (37 * SECOND, 42 * SECOND)
    assert (second.shipped_tick, second.returned_tick) == (77 * SECOND, 82 * SECOND)
    assert (first.port_reserved_tick, second.port_reserved_tick) == (7 * SECOND, 37 * SECOND)
    assert (first.port_reservation_ticks, second.port_reservation_ticks) == (
        30 * SECOND,
        40 * SECOND,
    )
    assert (first.port_service_ticks, second.port_service_ticks) == (25 * SECOND, 35 * SECOND)
    assert (first.paid_exposure_ticks, second.paid_exposure_ticks) == (42 * SECOND, 82 * SECOND)
    assert sum(w.paid_ticks + w.queue_ticks for w in result.at_end.workers) == 124 * SECOND


def test_one_buffer_releases_only_after_actual_pickup() -> None:
    profile = two_whole_jobs()
    profile = replace(profile, ports=(replace(profile.ports[0], buffer_ids=("whole-buffer",)),))
    result = WholeFlowEngine(profile, receipt_conveyor()).run(100 * SECOND, 200 * SECOND)
    first, second = result.at_end.whole_orders
    assert first.buffer_picked_tick == second.admitted_tick == 8 * SECOND
    assert second.buffered_tick == 15 * SECOND
    assert second.shipped_tick == 77 * SECOND


def test_end_cap_preserves_intact_buffer_stock_claim_and_paid_wait() -> None:
    result = WholeFlowEngine(two_whole_jobs(), receipt_conveyor()).run(20 * SECOND, 30 * SECOND)
    assert result.status == "partial"
    assert result.at_end.tick == 30 * SECOND
    assert len(result.at_end.inventory.claims) == 2
    second = result.at_end.whole_orders[1]
    assert second.wait_reason == "port_busy" and second.buffer_picked_tick is None
    assert second.paid_exposure_ticks == 30 * SECOND
    assert dict(result.at_end.balance.shipped_units_by_sku) == {}
