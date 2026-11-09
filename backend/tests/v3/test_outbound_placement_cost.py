"""Independent line-graph cost: one consumption cannot repay a complete transfer."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.outbound_placement_cost import price_candidate
from app.v3.outbound_placement_models import PlacementActor, PlacementCostFacts
from app.v3.runtime_graph import Arc, DirectedGraph


def line_graph() -> DirectedGraph:
    rows = (("h", "t", F(2)), ("t", "s", F(8)))
    arcs = tuple(
        Arc(
            a + b,
            a,
            b,
            length,
            length,
            modes=frozenset({"pedestrian"}),
            cargo_classes=frozenset({"STANDARD_CARTON"}),
            clear_width_m=F(2),
            clear_height_m=F(3),
        )
        for x, y, length in rows
        for a, b in ((x, y), (y, x))
    )
    return DirectedGraph("hand", ("h", "t", "s"), arcs)


def facts() -> PlacementCostFacts:
    return PlacementCostFacts(
        PlacementActor("S01", "h", F(1), F(10)),
        "s",
        "t",
        "h",
        "h",
        "STANDARD_CARTON",
        (F(".6"), F(".4"), F(".3")),
        1000000,
        1000000,
        1000000,
        1000000,
        2000000,
        F(".7"),
        F("1.8"),
        F(".02"),
    )


def test_complete_transfer_22_beats_gross_saving_16_the_wrong_way() -> None:
    cost = price_candidate(line_graph(), facts())
    assert (cost.baseline_ticks, cost.adapted_ticks) == (25000000, 9000000)
    assert (cost.relocation_ticks, cost.gross_saving_ticks, cost.net_saving_ticks) == (
        22000000,
        16000000,
        -6000000,
    )
    assert len(cost.relocation) == 5 and len(cost.baseline) == len(cost.adapted) == 8
    assert sum(op.ticks for op in cost.relocation) == cost.relocation_ticks
    assert cost.relocation[-1].route is not None
    assert cost.relocation[-1].route.node_ids == ("t", "h")


def test_round_each_leg_before_summing() -> None:
    base = line_graph()
    arcs = tuple(
        replace(a, length_m=a.length_m / 3000000, cost_m=a.cost_m / 3000000) for a in base.arcs
    )
    cost = price_candidate(DirectedGraph("tiny", base.node_ids, arcs), facts())
    # 10/3, 8/3, 2/3 microseconds -> 4 + 3 + 1, not ceil(20/3)=7.
    assert cost.relocation_ticks == 2000008


def test_explicit_cargo_denial_is_not_a_shortcut() -> None:
    base = line_graph()
    graph = DirectedGraph(
        "denied", base.node_ids, tuple(replace(a, cargo_classes=frozenset()) for a in base.arcs)
    )
    with pytest.raises(ValueError, match="DIRECTED_ROUTE"):
        price_candidate(graph, facts())
