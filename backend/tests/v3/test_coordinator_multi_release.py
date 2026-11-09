"""Actual cart return and picker return are separate physical release boundaries."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.coordinator_models import CoordinatorProfile
from app.v3.runtime_graph import Arc, DirectedGraph
from app.v3.whole_flow_validate import validate_whole_flow
from tests.v3.test_coordinator_multi_fixtures import multi_profile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor


def distant_picker_profile() -> CoordinatorProfile:
    p = multi_profile(candidate=False, two_carts=True)
    flow, resources = p.world.receipts.flow, p.unit_resources
    assert resources is not None
    arcs = (
        *flow.graph.arcs,
        *(
            Arc(f"picker:{a}:{b}", a, b, F(4), F(4), modes=frozenset({"pedestrian"}))
            for a, b in (("H02", "H"), ("H", "H02"))
        ),
    )
    graph = DirectedGraph("paid-picker-home", (*flow.graph.node_ids, "H02"), arcs)
    flow = replace(
        flow,
        graph=graph,
        actors=tuple(replace(a, home="H02") if a.actor_id == "P02" else a for a in flow.actors),
        orders=(replace(flow.orders[1], arrival_tick=98 * SECOND),),
    )
    return replace(
        p,
        unit_resources=replace(resources, assignments=(resources.assignments[1],)),
        world=replace(p.world, receipts=replace(p.world.receipts, flow=flow)),
    )


@pytest.mark.parametrize("cap", [122, 125, 126])
def test_cart_releases_at_actual_home_before_picker_finishes_paid_walk(cap: int) -> None:
    result = CoordinatorEngine(distant_picker_profile(), receipt_conveyor()).run(
        cap * SECOND, cap * SECOND
    )
    snap = result.at_end
    cart = next(c for c in snap.carts if c.cart_id == "CART02")
    picker = next(w for w in snap.workers if w.actor_id == "P02")
    assert cart.node == "H" and cart.operation is None and cart.order_id is None
    assert dict(snap.cart_releases) == {"O2": 122 * SECOND}
    if cap < 126:
        assert picker.order_id == "O2" and picker.operation is not None
        assert picker.operation.kind == "picker_return" and picker.operation.cart_id is None
        assert (picker.operation.start_tick, picker.operation.planned_end_tick) == (
            122 * SECOND,
            126 * SECOND,
        )
        assert picker.paid_ticks == (cap - 98) * SECOND
    else:
        assert picker.node == "H02" and picker.order_id is None
        assert picker.paid_ticks == 28 * SECOND


def test_returned_cart_can_pass_to_another_picker_while_first_walks_home() -> None:
    p = distant_picker_profile()
    original = multi_profile(candidate=False, two_carts=True)
    r, flow = p.unit_resources, p.world.receipts.flow
    assert r is not None and original.unit_resources is not None
    first = replace(original.world.receipts.flow.orders[0], arrival_tick=122 * SECOND)
    assignment = replace(original.unit_resources.assignments[0], cart_id="CART02")
    p = replace(
        p,
        unit_resources=replace(r, assignments=(assignment, *r.assignments)),
        world=replace(
            p.world,
            receipts=replace(p.world.receipts, flow=replace(flow, orders=(first, *flow.orders))),
        ),
    )
    result = CoordinatorEngine(p, receipt_conveyor()).run(125 * SECOND, 125 * SECOND)
    workers = {w.actor_id: w for w in result.at_end.workers}
    cart = next(c for c in result.at_end.carts if c.cart_id == "CART02")
    assert cart.order_id == "O1" and cart.operation is workers["P01"].operation
    assert workers["P02"].order_id == "O2" and workers["P02"].operation is not None
    assert workers["P02"].operation.cart_id is None
    assert dict(result.at_end.cart_releases) == {"O2": 122 * SECOND}


def test_explicit_cart_release_handling_is_paid_before_reuse() -> None:
    p = distant_picker_profile()
    r = p.unit_resources
    assert r is not None
    p = replace(
        p,
        unit_resources=replace(r, carts=(r.carts[0], replace(r.carts[1], release_tick=2 * SECOND))),
    )
    result = CoordinatorEngine(p, receipt_conveyor()).run(123 * SECOND, 123 * SECOND)
    cart = next(c for c in result.at_end.carts if c.cart_id == "CART02")
    worker = next(w for w in result.at_end.workers if w.actor_id == "P02")
    assert cart.order_id == "O2" and cart.node == "H"
    assert worker.operation is not None and worker.operation.kind == "cart_release"
    assert (worker.operation.start_tick, worker.operation.planned_end_tick) == (
        122 * SECOND,
        124 * SECOND,
    )
    assert not result.at_end.cart_releases


def test_default_picker_also_pays_separate_home_route_without_relaxing_old_validator() -> None:
    p = distant_picker_profile()
    r, flow = p.unit_resources, p.world.receipts.flow
    assert r is not None
    flow = replace(
        flow,
        actors=tuple(replace(a, home="H02") if a.actor_id == "P01" else a for a in flow.actors),
    )
    p = replace(
        p,
        unit_resources=replace(r, assignments=(replace(r.assignments[0], picker_id="P01"),)),
        world=replace(p.world, receipts=replace(p.world.receipts, flow=flow)),
    )
    with pytest.raises(ValueError, match="cart home"):
        validate_whole_flow(p.world, receipt_conveyor())
    result = CoordinatorEngine(p, receipt_conveyor()).run(124 * SECOND, 124 * SECOND)
    picker = next(w for w in result.at_end.workers if w.actor_id == "P01")
    assert picker.operation is not None and picker.operation.kind == "picker_return"
    assert picker.operation.planned_end_tick == 126 * SECOND
    assert dict(result.at_end.cart_releases) == {"O2": 122 * SECOND}
