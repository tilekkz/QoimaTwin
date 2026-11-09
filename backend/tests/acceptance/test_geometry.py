"""Acceptance gates G1-G4 from 05_Acceptance_and_Demo.md section 2."""

from __future__ import annotations

from fractions import Fraction

import pytest

from app.contracts.layout import Layout
from app.navigation.shortest_paths import AllPairsPaths

pytestmark = pytest.mark.acceptance


@pytest.fixture(scope="module")
def paths(layout: Layout) -> AllPairsPaths:
    return AllPairsPaths.from_graph(layout.picker_graph)


def test_G1_graph_counts_reachability_and_reserve_access(
    layout: Layout, paths: AllPairsPaths
) -> None:
    # 05 section2 G1 / 01 section3:184 nodes,205 edges;288 racks * (1 pick +2 reserve).
    assert len(layout.picker_graph.nodes) == 184
    assert len(layout.picker_graph.edges) == 205
    pickfaces = [s for s in layout.slots if s.kind == "pickface"]
    reserves = [s for s in layout.slots if s.kind == "reserve"]
    assert len(pickfaces) == 288
    assert len(reserves) == 576
    for home in ("I01", "I02", "I03"):
        for slot in pickfaces:
            assert slot.service_node_id is not None
            assert paths.distance(home, slot.service_node_id) is not None
    assert all(s.service_node_id is None for s in reserves)


def test_G2_home_to_first_bay_is_four_metres(paths: AllPairsPaths) -> None:
    assert paths.distance("I01", "N_A01_Z16") == Fraction(4)
    assert paths.path("I01", "N_A01_Z16") == ("I01", "N_A01_Z14", "N_A01_Z16")


def test_G3_adjacent_aisle_requires_eight_point_five_metres(paths: AllPairsPaths) -> None:
    assert paths.distance("N_A01_Z16", "N_A02_Z16") == Fraction(17, 2)
    route = paths.path("N_A01_Z16", "N_A02_Z16")
    assert route == ("N_A01_Z16", "N_A01_Z14", "N_A02_Z14", "N_A02_Z16")


def test_G4_two_sku_round_trip_is_twenty_one_metres(paths: AllPairsPaths) -> None:
    total = (
        paths.require_distance("I01", "N_A01_Z16")
        + paths.require_distance("N_A01_Z16", "N_A02_Z16")
        + paths.require_distance("N_A02_Z16", "I01")
    )
    assert total == Fraction(21)
