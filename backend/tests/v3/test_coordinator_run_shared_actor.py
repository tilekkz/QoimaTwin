"""A released picker may later pack its own order through an explicit physical role intent."""

from dataclasses import replace
from fractions import Fraction

from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.coordinator_run import build_coordinator_run
from app.v3.coordinator_run_inputs import freeze_hand_inputs
from app.v3.runtime_graph import Arc, DirectedGraph
from tests.v3.test_coordinator_multi_fixtures import multi_profile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor


def test_same_actor_keeps_distinct_completed_picker_and_later_packing_plans() -> None:
    profile = multi_profile()
    flow, resources = profile.world.receipts.flow, profile.unit_resources
    assert resources is not None
    home = flow.cart.home
    arcs = tuple(
        Arc(f"same:{a}:{b}", a, b, Fraction(6), Fraction(6), modes=frozenset({"pedestrian"}))
        for a, b in ((home, "ST05"), ("ST05", home))
    )
    flow = replace(
        flow,
        graph=DirectedGraph("same-actor-hand", flow.graph.node_ids, (*flow.graph.arcs, *arcs)),
        actors=tuple(replace(a, home=home) if a.actor_id == "P11" else a for a in flow.actors),
    )
    profile = replace(
        profile,
        world=replace(profile.world, receipts=replace(profile.world.receipts, flow=flow)),
        intents=tuple(
            replace(i, restore_node=home) if i.actor_id == "P11" else i for i in profile.intents
        ),
        unit_resources=replace(
            resources,
            assignments=tuple(
                replace(a, picker_id="P11") if a.order_id == "O1" else a
                for a in resources.assignments
            ),
        ),
    )
    outcome = CoordinatorEngine(profile, receipt_conveyor()).run(300 * SECOND, 400 * SECOND)
    inputs = freeze_hand_inputs(profile, receipt_conveyor(), 300 * SECOND, 400 * SECOND)
    run = build_coordinator_run(inputs, outcome)
    packing = next(p for p in outcome.at_end.packing if p.order_id == "O1")
    assert (packing.actor_id, packing.role_intent_id) == ("P11", "I11")
    assert run["metrics"]["at_end"]["unit"]["completed_units"] == 6
