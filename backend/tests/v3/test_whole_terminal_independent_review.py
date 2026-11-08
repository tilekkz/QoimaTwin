"""Two actual hand ports share exact destination identities and one worker map."""

from dataclasses import replace

from app.v3.stock_models import StockOwner
from app.v3.whole_flow_engine import WholeFlowEngine
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor
from tests.v3.test_whole_flow_terminal_capacity import mixed_terminal_profile


def test_prefix_related_destinations_allow_two_actual_ports_without_false_blocking() -> None:
    profile = mixed_terminal_profile()
    flow = profile.receipts.flow
    flow = replace(flow, owners=(*flow.owners, StockOwner("shipped:extra", "shipped", 1)))
    profile = replace(
        profile,
        receipts=replace(profile.receipts, flow=flow),
        ports=(replace(profile.ports[0], shipped_owner="shipped:extra"),),
    )
    result = WholeFlowEngine(profile, receipt_conveyor()).run(181 * SECOND, 220 * SECOND)
    whole = result.at_end.whole_orders[0]
    assert whole.port_reserved_tick == 180 * SECOND
    assert whole.service_started_tick == 185 * SECOND
    assert whole.shipped_tick == 210 * SECOND
    assert whole.returned_tick == 215 * SECOND
    assert result.at_end.orders[0].shipped_tick == 192_170_000
    assert {("port:OUT_S_EXPRESS", "O1"), ("port:OUT_W_RETAIL", "W1")} <= set(
        result.at_horizon.leases
    )
    owners = {c.container_id: c.owner_id for c in result.at_end.stock.containers}
    assert (owners["P1"], owners["HU2"]) == ("shipped", "shipped:extra")
    assert result.status == "complete" and not result.at_end.leases


def test_whole_promise_first_blocks_parcel_before_and_after_actual_handoff() -> None:
    profile = mixed_terminal_profile()
    profile = replace(
        profile,
        orders=(replace(profile.orders[0], arrival_tick=160 * SECOND),),
        ports=(replace(profile.ports[0], shipper_ids=("S02",)),),
    )
    result = WholeFlowEngine(profile, receipt_conveyor()).run(181 * SECOND, 220 * SECOND)
    # Arrival160 + approach2/pick1/carry3/place1 = buffer167.
    # Buffer pick1/carry4/service25/return5 = service172, ship197, home202.
    whole = result.at_end.whole_orders[0]
    assert (whole.buffered_tick, whole.port_reserved_tick) == (167 * SECOND, 167 * SECOND)
    assert (whole.service_started_tick, whole.shipped_tick, whole.returned_tick) == (
        172 * SECOND,
        197 * SECOND,
        202 * SECOND,
    )
    for point in (result.at_horizon, result.at_end):
        parcel_worker = next(w for w in point.workers if w.actor_id == "S01")
        assert parcel_worker.node == "PORT" and parcel_worker.operation is None
        assert parcel_worker.waiting_since == 172_170_000
        assert point.orders[0].shipped_tick is None
        assert ("port:OUT_S_EXPRESS", "O1") not in point.leases
    owners = {c.container_id: c.owner_id for c in result.at_end.stock.containers}
    assert (owners["HU2"], owners["P1"]) == ("shipped", "actor:S01")
    assert result.status == "partial"
