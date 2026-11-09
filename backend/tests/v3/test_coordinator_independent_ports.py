"""Independent same-port queue and paid-return cap oracles, prepared before execution."""

from app.v3.coordinator_engine import CoordinatorEngine
from tests.v3.test_coordinator_independent_fixtures import separated_arrivals
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor


def test_two_shippers_share_one_port_and_wait_exactly_two_seconds() -> None:
    result = CoordinatorEngine(separated_arrivals(two_shippers=True), receipt_conveyor()).run(
        269 * SECOND, 300 * SECOND
    )
    workers = {worker.actor_id: worker for worker in result.at_horizon.workers}
    first, second = workers["S01"], workers["S02"]
    assert first.operation is not None and first.operation.kind == "shipping_service"
    assert (first.operation.start_tick, first.operation.planned_end_tick) == (
        250_170_000,
        270_170_000,
    )
    assert second.node == "PORT" and second.operation is None
    assert second.order_id == "O2" and second.waiting_since == 268_170_000
    assert dict(result.at_horizon.leases)["port:OUT_S_EXPRESS"] == "O1"
    assert dict(result.at_horizon.balance.shipped_units_by_sku) == {}
    assert tuple(order.shipped_tick for order in result.at_end.orders) == (
        270_170_000,
        290_170_000,
    )
    progress = {row.order_id: row for row in result.at_end.unit_progress}
    assert progress["O2"].shipper_returned_tick == 295_170_000
    assert result.business_complete_tick == 290_170_000
    assert result.resource_drained_tick == 295_170_000
    assert dict(result.at_end.balance.shipped_units_by_sku) == {"SKU1": 6}
    assert result.status == "complete" and result.constraint_violations == ()


def test_same_shipper_cap_keeps_actual_paid_return_after_all_goods_ship() -> None:
    result = CoordinatorEngine(separated_arrivals(), receipt_conveyor()).run(
        300 * SECOND, 303 * SECOND
    )
    assert dict(result.at_horizon.balance.shipped_units_by_sku) == {"SKU1": 3}
    assert dict(result.at_end.balance.shipped_units_by_sku) == {"SKU1": 6}
    assert tuple(order.shipped_tick for order in result.at_end.orders) == (
        270_170_000,
        301_170_000,
    )
    worker = next(row for row in result.at_end.workers if row.actor_id == "S01")
    operation = worker.operation
    assert operation is not None and operation.kind == "return"
    assert worker.node is None and worker.order_id == "O2"
    assert (operation.start_tick, operation.planned_end_tick) == (301_170_000, 306_170_000)
    assert "port:OUT_S_EXPRESS" not in dict(result.at_end.leases)
    progress = {row.order_id: row for row in result.at_end.unit_progress}
    assert progress["O1"].shipper_returned_tick == 275_170_000
    assert progress["O2"].shipper_returned_tick is None
    assert result.business_complete_tick == 301_170_000
    assert result.resource_drained_tick is None and result.status == "partial"
    assert result.staffing_status == "valid" and result.constraint_violations == ()
