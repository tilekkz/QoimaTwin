"""Independent directed 2/3/5 metre relocation oracle, with no source catalogue execution."""

from dataclasses import replace
from fractions import Fraction as F

from app.v3.relocation_models import RelocationJob, RelocationPlace, RelocationProfile
from app.v3.runtime_graph import Arc, DirectedGraph
from app.v3.stock_models import StockOwner
from app.v3.whole_profile_geometry import ROUTE_POLICY
from tests.v3.test_coordinator_fixtures import staffing_profile

SECOND = 1_000_000


def relocation_graph(graph: DirectedGraph) -> DirectedGraph:
    arcs = list(graph.arcs)
    for start, end, length in (("SLOT", "TARGET", 3), ("TARGET", "SH", 5), ("TARGET", "WB", 7)):
        arcs.append(
            Arc(
                f"relocate:{start}:{end}",
                start,
                end,
                F(length),
                F(length),
                modes=frozenset({"pedestrian"}),
                cargo_classes=frozenset({"SMALL_CARTON", "STANDARD_CARTON"}),
                clear_width_m=F(2),
                clear_height_m=F(3),
            )
        )
    return DirectedGraph("relocation-hand", (*graph.node_ids, "TARGET"), arcs)


def relocation_hand(
    *, whole_arrival: int | None = None, standard: bool = True
) -> RelocationProfile:
    coordinator = staffing_profile(whole_order=standard)
    world, flow = coordinator.world, coordinator.world.receipts.flow
    stock = replace(flow.stock, owners=(*flow.stock.owners, StockOwner("target", "slot", 1)))
    flow = replace(flow, graph=relocation_graph(flow.graph), stock=stock)
    orders = (
        () if whole_arrival is None else (replace(world.orders[0], arrival_tick=whole_arrival),)
    )
    world = replace(world, receipts=replace(world.receipts, flow=flow), orders=orders)
    coordinator = replace(coordinator, world=world, intents=())
    places = tuple(
        RelocationPlace(
            owner,
            node,
            (F(1), F(1), F(1)),
            F(15),
            F(".02"),
            module,
            F(100),
            10,
        )
        for owner, node, module in (("slot", "SLOT", "M1"), ("target", "TARGET", "M2"))
    )
    job = RelocationJob("N1", 0, "HU1", "slot", "target", "S01", 2 * SECOND, SECOND)
    return RelocationProfile(
        "relocation-hand-v1",
        "Independent 2/3/5 metre hand oracle",
        coordinator,
        (job,),
        ("S01",),
        places,
        ROUTE_POLICY,
        F(1),
        F(1),
    )
