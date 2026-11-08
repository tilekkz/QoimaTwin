"""Future offers require exact typed geometry and cannot promise operational heavy handling."""

from dataclasses import replace
from fractions import Fraction as F
from typing import cast

import pytest

from app.v3.receipt_flow_engine import ReceiptFlowEngine
from app.v3.receipt_flow_models import ReceiptPlace, ReceiptPort
from app.v3.runtime_graph import DirectedGraph
from tests.v3.test_receipt_flow_fixtures import receipt_conveyor, receipt_hand_profile


@pytest.mark.parametrize("field", ["place", "port"])
def test_untyped_nested_records_reject_as_input_errors(field: str) -> None:
    profile = receipt_hand_profile()
    if field == "place":
        profile = replace(profile, places=(cast(ReceiptPlace, {}),))
    else:
        profile = replace(profile, ports=(cast(ReceiptPort, {}),))
    with pytest.raises(ValueError, match="typed"):
        ReceiptFlowEngine(profile, receipt_conveyor())


@pytest.mark.parametrize(
    "failure", ["quantity_bool", "payload_bool", "slot_anchor", "reverse", "occupied"]
)
def test_bad_receipt_definition_geometry_or_route_fails_before_live_credit(failure: str) -> None:
    profile = receipt_hand_profile()
    if failure == "quantity_bool":
        offer = profile.receipts[0]
        profile = replace(
            profile,
            receipts=(
                replace(
                    offer, definition=replace(offer.definition, quantity_units=cast(int, True))
                ),
            ),
        )
    elif failure == "payload_bool":
        profile = replace(
            profile,
            places=(replace(profile.places[0], max_gross_kg=cast(F, True)), profile.places[1]),
        )
    elif failure == "slot_anchor":
        order = replace(profile.flow.orders[0], source_node="H")
        profile = replace(profile, flow=replace(profile.flow, orders=(order,)))
    elif failure == "reverse":
        graph = profile.flow.graph
        graph = DirectedGraph(
            graph.graph_id, graph.node_ids, (a for a in graph.arcs if a.arc_id != "RECEIVE-RH")
        )
        profile = replace(profile, flow=replace(profile.flow, graph=graph))
    else:
        stock = profile.flow.stock
        stock = replace(stock, containers=(replace(stock.containers[0], owner_id="new-slot"),))
        profile = replace(profile, flow=replace(profile.flow, stock=stock))
    with pytest.raises(ValueError):
        ReceiptFlowEngine(profile, receipt_conveyor())


@pytest.mark.parametrize(
    "archetype",
    ["STANDARD_CARTON", "HEAVY_BOX", "PALLET_LOAD", "IBC", "LONG_BUNDLE", "DRUM", "FRAGILE_CRATE"],
)
def test_whole_hu_accounting_does_not_grant_other_class_execution(archetype: str) -> None:
    profile = receipt_hand_profile()
    stock = profile.flow.stock
    tokens = tuple(
        replace(u, recipe=replace(u.recipe, archetype_id=archetype)) for u in stock.units
    )
    wrapper = stock.containers[0]
    wrapper = replace(wrapper, recipe=replace(wrapper.recipe, allowed_archetypes=(archetype,)))
    stock = replace(stock, units=tokens, containers=(wrapper,))
    profile = replace(profile, flow=replace(profile.flow, stock=stock, orders=()))
    with pytest.raises(ValueError, match="only SMALL receipt execution"):
        ReceiptFlowEngine(profile, receipt_conveyor())
