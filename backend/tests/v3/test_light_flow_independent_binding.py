"""Source-bound planning keeps real graph segments and pays the split source access."""

from fractions import Fraction as F
from functools import cache
from itertools import pairwise
from math import ceil

from app.v3.light_flow_models import FlowProfile
from app.v3.light_flow_plan import picker_plan
from tests.v3.test_light_flow_independent_source import source_document
from tests.v3.test_light_flow_source import source_profile


@cache
def bound_profile() -> FlowProfile:
    return source_profile()


def test_source_binder_retains_all_stock_and_both_l08_corridor_splits() -> None:
    profile = bound_profile()
    raw = source_document("layout-links-v3.json")["walk_graph"]
    originals = {a["arc_id"]: a for a in raw["arcs"]}
    arcs = {a.arc_id: a for a in profile.graph.arcs}
    assert set(arcs) == set(originals)
    for index in range(3):
        for direction in ("f", "r"):
            key = f"v3:ped-edge:0046:part:{index:03}:{direction}"
            arc, original = arcs[key], originals[key]
            assert (arc.source, arc.target) == (original["from_node_id"], original["to_node_id"])
            assert arc.length_m == F(str(original["length_m"]))
            assert arc.modes == frozenset(original["allowed_modes"])
    assert len(profile.stock.containers) == 530 and len(profile.stock.units) == 12256
    assert len(profile.source_hashes) == 15
    assert profile.source_revision == "22296bcf2c6bac5ade4cefc7c05c2b97831ec6ec"
    assert profile.cart.park == "v3:service:CART_PARK"
    assert profile.intake_node == "v3:service:CONVEYOR_IN"
    assert profile.output_node == "v3:service:CONVEYOR_OUT"
    assert profile.station.node == "v3:service:PK06"


def test_distinct_cart_and_worker_source_nodes_have_paid_loaded_access_routes() -> None:
    profile = bound_profile()
    order = profile.orders[0]
    picker = next(actor for actor in profile.actors if actor.actor_id == profile.picker_id)
    steps = picker_plan(profile, picker, order)
    assert order.source_node != order.cart_source_node
    phases = {step.kind: step for step in steps if step.kind.startswith("source_")}
    assert phases["source_park"].target == order.cart_source_node
    assert phases["source_detach"].target == order.cart_source_node
    assert phases["source_attach"].target == order.cart_source_node
    pick_index = next(i for i, step in enumerate(steps) if step.kind == "pick")
    incoming, pick, outgoing = steps[pick_index - 1 : pick_index + 2]
    assert pick.target == order.source_node and pick.cart_id is None
    assert incoming.route is not None and outgoing.route is not None
    assert incoming.route.node_ids[0] == outgoing.route.node_ids[-1] == order.cart_source_node
    assert incoming.route.node_ids[-1] == outgoing.route.node_ids[0] == order.source_node
    assert incoming.carrying_id == pick.carrying_id == outgoing.carrying_id == order.carrier_id
    assert incoming.duration > 0 and outgoing.duration > 0
    assert phases["source_park"].duration == profile.times.park
    assert phases["source_detach"].duration == profile.times.detach
    assert phases["source_attach"].duration == profile.times.attach


def test_every_source_human_route_uses_declared_connected_arcs_and_paid_length() -> None:
    profile = bound_profile()
    picker = next(actor for actor in profile.actors if actor.actor_id == profile.picker_id)
    steps = picker_plan(profile, picker, profile.orders[0])
    raw = source_document("layout-links-v3.json")["walk_graph"]
    originals = {a["arc_id"]: a for a in raw["arcs"]}
    previous = picker.home
    for step in steps:
        if step.route is None:
            assert step.target == previous
        else:
            route = step.route
            assert route.node_ids[0] == previous and route.node_ids[-1] == step.target
            path = [originals[key] for key in route.arc_ids]
            assert all(a["to_node_id"] == b["from_node_id"] for a, b in pairwise(path))
            mode = "manual_cart" if step.cart_id else "pedestrian"
            assert all(mode in arc["allowed_modes"] for arc in path)
            length = sum((F(str(arc["length_m"])) for arc in path), F(0))
            speed = (
                min(picker.speed_m_s, profile.cart.speed_m_s) if step.cart_id else picker.speed_m_s
            )
            assert step.duration == ceil(length / speed * 1_000_000)
        previous = step.target
