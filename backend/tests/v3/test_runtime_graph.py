"""Directed route and admission-filter oracles use small manually defined graphs."""

from fractions import Fraction

import pytest

from app.v3.runtime_graph import Arc, DirectedGraph, RouteRequirements


def arc(name: str, source: str, target: str, cost: int = 1, **kwargs: object) -> Arc:
    return Arc(name, source, target, Fraction(cost), Fraction(cost), **kwargs)  # type: ignore[arg-type]


def test_direction_self_route_and_unreachable_are_distinct() -> None:
    graph = DirectedGraph("walk", ("a", "b", "c"), (arc("ab", "a", "b", 2),))
    route = graph.shortest_path("a", "b")
    assert route is not None and route.node_ids == ("a", "b")
    assert route.arc_ids == ("ab",) and route.cost_m == 2
    assert graph.shortest_path("b", "a") is None
    assert graph.shortest_path("a", "c") is None
    same = graph.shortest_path("a", "a")
    assert same is not None and same.arc_ids == () and same.length_m == 0


def test_equal_routes_are_stable_under_input_permutation() -> None:
    arcs = (arc("ac", "a", "c"), arc("cd", "c", "d"), arc("ab", "a", "b"), arc("bd", "b", "d"))
    one = DirectedGraph("walk", ("a", "b", "c", "d"), arcs).shortest_path("a", "d")
    two = DirectedGraph("walk", ("d", "c", "b", "a"), tuple(reversed(arcs))).shortest_path("a", "d")
    assert one == two
    assert one is not None and one.arc_ids == ("ab", "bd") and one.cost_m == 2


@pytest.mark.parametrize(
    "requirement",
    [
        RouteRequirements(mode="manual_cart"),
        RouteRequirements(profile="loaded_max"),
        RouteRequirements(cargo="HEAVY_BOX"),
        RouteRequirements(min_clear_width_m=Fraction(2)),
        RouteRequirements(min_clear_height_m=Fraction(3)),
    ],
)
def test_incompatible_shortcut_is_removed_before_scoring(requirement: RouteRequirements) -> None:
    admitted = {
        "modes": frozenset({"manual_cart"}),
        "profiles": frozenset({"loaded_max"}),
        "cargo_classes": frozenset({"HEAVY_BOX"}),
        "clear_width_m": Fraction(2),
        "clear_height_m": Fraction(3),
    }
    graph = DirectedGraph(
        "test",
        ("a", "b", "c"),
        (
            arc("shortcut", "a", "c"),
            arc("ab", "a", "b", 4, **admitted),
            arc("bc", "b", "c", 4, **admitted),
        ),
    )
    route = graph.shortest_path("a", "c", requirement)
    assert route is not None and route.arc_ids == ("ab", "bc") and route.cost_m == 8


def test_loaded_cargo_never_uses_bare_only_edge() -> None:
    graph = DirectedGraph(
        "vehicle", ("a", "b"), (arc("bare", "a", "b", profiles=frozenset({"unloaded_bare"})),)
    )
    assert graph.shortest_path("a", "b", RouteRequirements(profile="unloaded_bare")) is not None
    assert graph.shortest_path("a", "b", RouteRequirements(cargo="IBC")) is None


@pytest.mark.parametrize(
    "nodes,arcs",
    [
        (("a", "a"), ()),
        (("a",), (arc("ab", "a", "b"),)),
        (("a", "b"), (arc("ab", "a", "b"), arc("ab", "b", "a"))),
        (("a", "b"), (arc("ab", "a", "b", -1),)),
    ],
)
def test_invalid_graph_fails_before_any_route(
    nodes: tuple[str, ...], arcs: tuple[Arc, ...]
) -> None:
    with pytest.raises(ValueError):
        DirectedGraph("walk", nodes, arcs)


def test_unknown_nodes_are_input_errors() -> None:
    with pytest.raises(ValueError):
        DirectedGraph("walk", ("a",), ()).shortest_path("missing", "a")


def test_empty_graph_returns_no_path_instead_of_zero_distance_success() -> None:
    assert DirectedGraph("walk", (), ()).shortest_path("a", "a") is None
