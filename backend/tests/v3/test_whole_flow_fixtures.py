"""Whole-HU travel and service numbers fixed by hand before the runtime exists."""

from dataclasses import replace
from fractions import Fraction as F

from app.v3.receipt_flow_models import ReceiptFlowProfile, ReceiptPlace
from app.v3.runtime_graph import Arc, DirectedGraph
from app.v3.stock_models import StockOwner, UnitRecipe
from app.v3.whole_flow_models import WholeFlowProfile, WholeHUOrder, WholeHUPort
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_hand_profile


def whole_hand_profile(archetype: str = "STANDARD_CARTON") -> WholeFlowProfile:
    receipt = receipt_hand_profile()
    flow = receipt.flow
    stock = flow.stock
    if archetype == "STANDARD_CARTON":
        recipe = UnitRecipe(archetype, (F(".10"), F(".08"), F(".06")), F(".20"), F(".05"))
        wrapper = replace(
            stock.containers[0].recipe,
            recipe_id="hand-standard-wrapper-v1",
            outer=(F(".60"), F(".40"), F(".30")),
            tare_kg=F(".35"),
            max_gross_kg=F("6.35"),
            allowed_archetypes=(archetype,),
        )
        stock = replace(
            stock,
            units=tuple(replace(u, recipe=recipe) for u in stock.units),
            containers=(replace(stock.containers[0], recipe=wrapper),),
        )
    owners = (
        *tuple(
            replace(o, kind="worker") if o.owner_id in {"actor:P01", "actor:S01"} else o
            for o in flow.owners
        ),
        StockOwner("actor:S02", "worker", 1),
        StockOwner("whole-buffer", "buffer", 1),
    )
    actors = tuple(replace(a, home="SH") if a.actor_id == "S02" else a for a in flow.actors)
    flow = replace(
        flow, stock=stock, owners=owners, actors=actors, orders=(), graph=whole_graph(flow.graph)
    )
    receipts = ReceiptFlowProfile(flow, (), (), (), SECOND, SECOND)
    places = tuple(
        ReceiptPlace(owner, node, (F(1), F(1), F(1)), F(15), F(".02"))
        for owner, node in (("slot", "SLOT"), ("whole-buffer", "WB"))
    )
    port = WholeHUPort(
        "OUT_W_RETAIL",
        "WP",
        (("SMALL_CARTON", 25 * SECOND), ("STANDARD_CARTON", 35 * SECOND)),
        ((0, 28800 * SECOND),),
        ("whole-buffer",),
        ("S01", "S02"),
        "shipped",
    )
    return WholeFlowProfile(
        receipts, (WholeHUOrder("W1", 0, "HU1", port.port_id),), (port,), places, SECOND, SECOND
    )


def whole_graph(graph: DirectedGraph) -> DirectedGraph:
    arcs = list(graph.arcs)
    for a, b, length in (("SH", "SLOT", 2), ("SLOT", "WB", 3), ("WB", "WP", 4), ("WP", "SH", 5)):
        for source, target in ((a, b), (b, a)):
            arcs.append(
                Arc(
                    f"whole:{source}-{target}",
                    source,
                    target,
                    F(length),
                    F(length),
                    modes=frozenset({"pedestrian"}),
                    cargo_classes=frozenset({"SMALL_CARTON", "STANDARD_CARTON"}),
                    clear_width_m=F(2),
                    clear_height_m=F(3),
                )
            )
    return DirectedGraph(
        "hand-whole", sorted({n for a in arcs for n in (a.source, a.target)}), arcs
    )
