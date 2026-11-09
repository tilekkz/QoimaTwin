"""A single hand graph joins receipt and picking before any engine result exists."""

from dataclasses import replace
from fractions import Fraction as F
from functools import cache

from app.v3.conveyor_models import ConveyorSource
from app.v3.light_flow_models import FlowProfile
from app.v3.receipt_flow_models import ReceiptFlowProfile, ReceiptOffer, ReceiptPlace, ReceiptPort
from app.v3.runtime_graph import Arc, DirectedGraph
from app.v3.stock_models import Placement, StockOwner
from app.v3.stock_receipts import ReceiptDefinition
from tests.v3.test_belt_runtime import source_catalog
from tests.v3.test_light_flow_fixtures import hand_profile

SECOND = 1_000_000


@cache
def receipt_conveyor() -> ConveyorSource:
    """All new hand tests share this immutable source; no test mutates its fields."""
    return source_catalog()


def joined_hand_graph(flow: FlowProfile) -> DirectedGraph:
    arcs = list(flow.graph.arcs)
    for a, b, distance in (("RH", "RECEIVE", 2), ("RECEIVE", "BUFFER", 3), ("BUFFER", "SLOT", 5)):
        for source, target in ((a, b), (b, a)):
            arcs.append(
                Arc(
                    f"{source}-{target}",
                    source,
                    target,
                    F(distance),
                    F(distance),
                    modes=frozenset({"pedestrian"}),
                    cargo_classes=frozenset({"SMALL_CARTON"}),
                    clear_width_m=F(2),
                    clear_height_m=F(3),
                )
            )
    return DirectedGraph(
        "hand-receipt-flow", sorted({n for a in arcs for n in (a.source, a.target)}), arcs
    )


def receipt_hand_profile(*, arrival_tick: int = 0) -> ReceiptFlowProfile:
    flow = hand_profile()
    units = tuple(Placement(f"HU2:unit:{i + 1:04d}", (F(7 * i, 100), F(0), F(0))) for i in range(3))
    order = replace(
        flow.orders[0], source_hu="HU2", carrier_placements=units, package_placements=units
    )
    actors = tuple(replace(a, home="RH") if a.actor_id == "R01" else a for a in flow.actors)
    extra = (
        StockOwner("actor:R01", "worker", 1),
        StockOwner("receipt-buffer", "buffer", 1),
        StockOwner("new-slot", "slot", 1),
    )
    flow = replace(
        flow,
        graph=joined_hand_graph(flow),
        actors=actors,
        owners=flow.owners + extra,
        orders=(order,),
    )
    places = tuple(
        ReceiptPlace(owner, node, (F(1), F(1), F(1)), F(15), F(".02"))
        for owner, node in (("receipt-buffer", "BUFFER"), ("new-slot", "SLOT"))
    )
    port = ReceiptPort(
        "IN_E_PARCEL", "RECEIVE", 10 * SECOND, ((0, 28800 * SECOND),), ("receipt-buffer",), ("R01",)
    )
    offer = ReceiptOffer(
        ReceiptDefinition("R1", "HU2", "SKU1", "LOT2", 24), arrival_tick, port.port_id, "new-slot"
    )
    return ReceiptFlowProfile(flow, (port,), places, (offer,), SECOND, SECOND)
