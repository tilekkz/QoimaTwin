"""B1 explicit hand staffing paths; no goods work or analytical-cover execution shortcut."""

from dataclasses import replace
from fractions import Fraction as F

from app.v3.coordinator_models import CoordinatorProfile, RoleIntent, RoleStation
from app.v3.light_flow_models import FlowProfile
from app.v3.runtime_graph import Arc, DirectedGraph
from app.v3.staff_registry import compile_staff_registry
from app.v3.stock_models import StockOwner
from tests.v3.test_staff_registry_fixtures import SECOND, registry_document
from tests.v3.test_whole_flow_fixtures import whole_hand_profile


def staffing_graph(flow: FlowProfile) -> DirectedGraph:
    arcs = list(flow.graph.arcs)
    for home, station, length in (("H11", "ST05", 6), ("H12", "PACK", 9)):
        for start, end in ((home, station), (station, home)):
            arcs.append(
                Arc(
                    f"staff:{start}:{end}",
                    start,
                    end,
                    F(length),
                    F(length),
                    modes=frozenset({"pedestrian"}),
                )
            )
    nodes = sorted(
        set(flow.graph.node_ids) | {f"ST{i:02}" for i in range(1, 6)} | {"H11", "H12", "REST05"}
    )
    return DirectedGraph("staff-hand-v1", nodes, arcs)


def staffing_profile(*, whole_order: bool = False) -> CoordinatorProfile:
    whole = whole_hand_profile("STANDARD_CARTON" if whole_order else "SMALL_CARTON")
    flow = whole.receipts.flow
    actors = tuple(
        replace(
            a,
            home={"P11": "H11", "P12": "H12", "K05": "REST05"}.get(a.actor_id, a.home),
            speed_m_s=F(3, 2) if a.actor_id in {"P11", "P12"} else a.speed_m_s,
        )
        for a in flow.actors
    )
    owners = flow.owners + tuple(StockOwner(f"bench{i:02}", "workstation", 1) for i in range(1, 6))
    flow = replace(flow, graph=staffing_graph(flow), actors=actors, owners=owners)
    world = replace(
        whole,
        receipts=replace(whole.receipts, flow=flow),
        orders=whole.orders if whole_order else (),
    )
    stations = tuple(
        RoleStation(
            f"PK{i:02}", f"ST{i:02}" if i < 6 else "PACK", f"bench{i:02}" if i < 6 else "bench"
        )
        for i in range(1, 7)
    )
    intents = (
        RoleIntent("I11", "P11", "PK05", 100 * SECOND, 156 * SECOND, 160 * SECOND, "H11"),
        RoleIntent("I12", "P12", "PK06", 100 * SECOND, 154 * SECOND, 160 * SECOND, "H12"),
    )
    return CoordinatorProfile(
        "hand-staff-v1",
        "explicit hand staffing proposal",
        world,
        compile_staff_registry(registry_document()),
        stations,
        intents,
    )
