"""A lease must bind a typed owner/job without ambiguous separator concatenation."""

from dataclasses import replace

from app.v3.whole_flow_engine import WholeFlowEngine
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor
from tests.v3.test_whole_flow_independent_capacity_ids import _separate_ports


def test_colon_bearing_owner_and_job_ids_do_not_alias_resource_identity() -> None:
    profile = _separate_ports()
    profile = replace(
        profile, orders=(profile.orders[0], replace(profile.orders[1], job_id="extra:W1"))
    )
    result = WholeFlowEngine(profile, receipt_conveyor()).run(20 * SECOND, 100 * SECOND)
    first, second = result.at_end.whole_orders
    assert first.port_reserved_tick == second.port_reserved_tick == 7 * SECOND
    assert (first.shipped_tick, second.shipped_tick) == (37 * SECOND, 47 * SECOND)
    assert not result.at_end.leases and not result.at_end.inventory.claims
