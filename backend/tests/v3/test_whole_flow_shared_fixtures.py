"""Two original wrappers or one future STANDARD wrapper on the same hand graph."""

from dataclasses import replace

from app.v3.runtime_graph import DirectedGraph
from app.v3.stock_models import StockOwner
from app.v3.whole_flow_models import WholeFlowProfile, WholeHUOrder
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_hand_profile
from tests.v3.test_whole_flow_fixtures import whole_hand_profile


def two_whole_jobs() -> WholeFlowProfile:
    small, standard = whole_hand_profile("SMALL_CARTON"), whole_hand_profile()
    flow = small.receipts.flow
    new_hu = replace(
        standard.receipts.flow.stock.containers[0], container_id="HU3", owner_id="slot2"
    )
    new_units = tuple(
        replace(u, unit_id="STD:" + u.unit_id, origin_hu="HU3", sku_id="SKU2", lot_id="LOT3")
        for u in standard.receipts.flow.stock.units
    )
    stock = replace(
        flow.stock,
        containers=(*flow.stock.containers, new_hu),
        units=flow.stock.units + new_units,
        owners=(*flow.stock.owners, StockOwner("slot2", "slot", 1)),
    )
    owners = tuple(replace(o, capacity=2) if o.owner_id == "shipped" else o for o in flow.owners)
    owners += (StockOwner("whole-buffer2", "buffer", 1),)
    flow = replace(flow, stock=stock, owners=owners)
    places = (
        *small.places,
        replace(small.places[0], owner_id="slot2"),
        replace(small.places[1], owner_id="whole-buffer2"),
    )
    port = replace(small.ports[0], buffer_ids=("whole-buffer", "whole-buffer2"))
    return replace(
        small,
        receipts=replace(small.receipts, flow=flow),
        ports=(port,),
        places=places,
        orders=(*small.orders, WholeHUOrder("W2", 0, "HU3", port.port_id)),
    )


def standard_receipt_chain() -> WholeFlowProfile:
    whole = whole_hand_profile()
    template = receipt_hand_profile()
    flow = whole.receipts.flow
    arcs = [
        replace(a, cargo_classes=frozenset({"SMALL_CARTON", "STANDARD_CARTON"}))
        for a in flow.graph.arcs
    ]
    flow = replace(flow, graph=DirectedGraph("hand-standard-receipt", flow.graph.node_ids, arcs))
    port = replace(template.ports[0], port_id="IN_N_STANDARD", service_tick=18 * SECOND)
    offer = replace(template.receipts[0], port_id=port.port_id)
    receipt = replace(template, flow=flow, ports=(port,), receipts=(offer,))
    return replace(
        whole,
        receipts=receipt,
        orders=(replace(whole.orders[0], hu_id="HU2"),),
        places=(*whole.places, template.places[1]),
    )
