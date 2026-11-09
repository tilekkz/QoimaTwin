"""Distinct declared owner IDs remain distinct even when one is a textual prefix."""

from dataclasses import replace
from fractions import Fraction

from app.v3.runtime_graph import DirectedGraph
from app.v3.stock_models import StockOwner
from app.v3.whole_flow_engine import WholeFlowEngine
from app.v3.whole_flow_models import WholeFlowProfile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor
from tests.v3.test_whole_flow_shared_fixtures import two_whole_jobs


def _separate_ports() -> WholeFlowProfile:
    profile = two_whole_jobs()
    flow = profile.receipts.flow
    template = next(a for a in flow.graph.arcs if a.arc_id == "whole:WB-WP")
    arcs = list(flow.graph.arcs)
    for source, target, length in (("WB", "WP2", 4), ("WP2", "SH", 5)):
        for start, end in ((source, target), (target, source)):
            arcs.append(
                replace(
                    template,
                    arc_id=f"second:{start}-{end}",
                    source=start,
                    target=end,
                    length_m=Fraction(length),
                    cost_m=Fraction(length),
                )
            )
    graph = DirectedGraph("two-independent-bays", (*flow.graph.node_ids, "WP2"), arcs)
    owners = tuple(replace(o, capacity=1) if o.owner_id == "shipped" else o for o in flow.owners)
    owners += (StockOwner("shipped:extra", "shipped", 1),)
    first = replace(profile.ports[0], buffer_ids=("whole-buffer",), shipped_owner="shipped:extra")
    second = replace(
        first,
        port_id="OUT_SECOND",
        node_id="WP2",
        buffer_ids=("whole-buffer2",),
        shipped_owner="shipped",
    )
    flow = replace(flow, graph=graph, owners=owners)
    return replace(
        profile,
        receipts=replace(profile.receipts, flow=flow),
        ports=(first, second),
        orders=(profile.orders[0], replace(profile.orders[1], port_id=second.port_id)),
    )


def test_separate_shipped_owners_do_not_share_reservations_by_string_prefix() -> None:
    result = WholeFlowEngine(_separate_ports(), receipt_conveyor()).run(20 * SECOND, 100 * SECOND)
    first, second = result.at_end.whole_orders
    # Both reach their dedicated buffers7, pay pickup1+approach4, then service25/35.
    assert first.port_reserved_tick == second.port_reserved_tick == 7 * SECOND
    assert (first.shipped_tick, second.shipped_tick) == (37 * SECOND, 47 * SECOND)
    assert (first.returned_tick, second.returned_tick) == (42 * SECOND, 52 * SECOND)
    assert result.status == "complete" and result.at_end.tick == 52 * SECOND
    assert dict(result.at_end.balance.shipped_units_by_sku) == {"SKU1": 24, "SKU2": 24}
    assert not result.at_end.leases and not result.at_end.inventory.claims
