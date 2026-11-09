"""Prewritten shared-bay oracle: parcel frees201.17; whole ships241.17 and returns246.17."""

from dataclasses import replace

from app.v3.whole_flow_engine import WholeFlowEngine
from tests.v3.test_light_flow_fixtures import hand_orders
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor
from tests.v3.test_whole_flow_shared_fixtures import two_whole_jobs


def test_shared_out_w_bay_blocks_s02_whole_behind_s01_parcel_service() -> None:
    profile = two_whole_jobs()
    flow = profile.receipts.flow
    flow = replace(
        flow,
        orders=hand_orders(1),
        port=replace(flow.port, port_id="OUT_W_RETAIL", node="WP", service_tick=25 * SECOND),
    )
    order = replace(profile.orders[1], arrival_tick=180 * SECOND)
    port = replace(profile.ports[0], shipper_ids=("S02",))
    profile = replace(
        profile, receipts=replace(profile.receipts, flow=flow), orders=(order,), ports=(port,)
    )
    result = WholeFlowEngine(profile, receipt_conveyor()).run(190 * SECOND, 300 * SECOND)
    whole = result.at_end.whole_orders[0]
    assert whole.buffered_tick == 187 * SECOND
    assert result.at_horizon.whole_orders[0].wait_reason == "port_busy"
    assert dict(result.at_horizon.leases)["port:OUT_W_RETAIL"] == "O1"
    assert result.at_end.orders[0].shipped_tick == 201_170_000
    assert whole.port_reserved_tick == 201_170_000
    assert whole.service_started_tick == 206_170_000
    assert (whole.shipped_tick, whole.returned_tick) == (241_170_000, 246_170_000)
    assert (whole.port_reservation_ticks, whole.port_service_ticks) == (40 * SECOND, 35 * SECOND)
    assert whole.paid_exposure_ticks == 66_170_000
    assert dict(result.at_end.balance.shipped_units_by_sku) == {"SKU1": 3, "SKU2": 24}
    assert not result.at_end.leases and not result.at_end.inventory.claims
