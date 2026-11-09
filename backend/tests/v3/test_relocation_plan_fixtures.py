"""Independent 2/3/5 metre directed relocation triangle; no engine execution."""

from dataclasses import replace
from fractions import Fraction as F

from app.v3.relocation_models import RelocationJob, RelocationPlace, RelocationProfile
from app.v3.runtime_graph import Arc, DirectedGraph
from app.v3.stock_models import StockOwner
from app.v3.whole_profile_geometry import ROUTE_POLICY
from tests.v3.test_coordinator_fixtures import staffing_profile


def hand_relocation() -> RelocationProfile:
    common = staffing_profile()
    flow = common.world.receipts.flow
    graph = DirectedGraph("relocation-hand", ("SH", "SLOT", "DEST"), _arcs())
    stock = replace(flow.stock, owners=(*flow.stock.owners, StockOwner("target", "slot", 1)))
    flow = replace(flow, graph=graph, stock=stock)
    common = replace(
        common, world=replace(common.world, receipts=replace(common.world.receipts, flow=flow))
    )
    places = tuple(
        RelocationPlace(owner, node, (F(1), F(1), F(1)), F(15), F(0), module, F(15), 1)
        for owner, node, module in (("slot", "SLOT", "M1"), ("target", "DEST", "M2"))
    )
    return RelocationProfile(
        "hand-relocation",
        "independent directed triangle",
        common,
        (RelocationJob("MOVE", 0, "HU1", "slot", "target", "S01", 2_000_000, 1_000_000),),
        ("S01",),
        places,
        ROUTE_POLICY,
        F(7, 10),
        F(9, 5),
    )


def _arcs() -> tuple[Arc, ...]:
    return tuple(
        Arc(
            name,
            start,
            end,
            F(length),
            F(length),
            frozenset({"pedestrian"}),
            cargo_classes=frozenset({"SMALL_CARTON"}),
            clear_width_m=F(1),
            clear_height_m=F(2),
        )
        for name, start, end, length in (
            ("a", "SH", "SLOT", 2),
            ("b", "SLOT", "DEST", 3),
            ("c", "DEST", "SH", 5),
        )
    )
