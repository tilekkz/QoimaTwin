"""A pedestrian-only shelf terminal requires paid detach/carry/reattach around the cart."""

from dataclasses import replace
from fractions import Fraction as F

from app.v3.light_flow_engine import LightFlowEngine
from app.v3.runtime_graph import Arc, DirectedGraph
from tests.v3.test_belt_runtime import source_catalog
from tests.v3.test_light_flow_fixtures import hand_profile


def test_separate_cart_and_worker_source_anchors_add_five_paid_seconds() -> None:
    profile = hand_profile()
    arcs = [
        replace(
            a,
            source="CARTSLOT" if a.source == "SLOT" else a.source,
            target="CARTSLOT" if a.target == "SLOT" else a.target,
        )
        for a in profile.graph.arcs
    ]
    for source, target in (("CARTSLOT", "SLOT"), ("SLOT", "CARTSLOT")):
        arcs.append(
            Arc(
                source + target,
                source,
                target,
                F(1),
                F(1),
                modes=frozenset({"pedestrian"}),
                clear_width_m=F(1),
                clear_height_m=F(3),
            )
        )
    graph = DirectedGraph("separate-access", (*profile.graph.node_ids, "CARTSLOT"), arcs)
    order = replace(profile.orders[0], cart_source_node="CARTSLOT")
    result = LightFlowEngine(replace(profile, graph=graph, orders=(order,)), source_catalog()).run(
        200_000_000, 230_000_000
    )
    assert result.status == "complete" and result.at_end.tick == 202_170_000
    assert next(e.tick for e in result.events if e.kind == "picked") == 9_000_000
    assert next(e.tick for e in result.events if e.kind == "intake_handoff") == 18_000_000
    pick = next(
        e
        for e in result.events
        if e.kind == "operation_started" and e.operation and e.operation.kind == "pick"
    )
    assert pick.operation is not None and pick.operation.source_node == "SLOT"
    assert pick.operation.cart_id is None
    assert all(
        e.operation.target_node != "SLOT"
        for e in result.events
        if e.kind == "operation_started" and e.operation and e.operation.cart_id
    )
