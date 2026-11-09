"""Frozen ABC and slot geometry (01 §9). Expected numbers are hand arithmetic on the layout."""

from __future__ import annotations

from collections import Counter
from fractions import Fraction
from pathlib import Path

import pytest

from app.contracts.assignment import Assignment
from app.contracts.layout import Layout
from app.planning import PlanningGeometry, PlanningInputError, build_frozen_abc


@pytest.fixture(scope="module")
def geometry(layout: Layout) -> PlanningGeometry:
    return PlanningGeometry.from_layout(layout)


@pytest.fixture(scope="module")
def example(contracts_dir: Path) -> Assignment:
    return Assignment.from_json_text((contracts_dir / "assignment.example.json").read_bytes())


def test_mean_home_round_trip_matches_hand_arithmetic(geometry: PlanningGeometry) -> None:
    # (2/3)(4 + 22 + 40) = 44 and (2/3)(71.5 + 53.5 + 35.5) = 107
    assert geometry.slot_cost("S_A01_B01_L_01") == Fraction(44)
    assert geometry.slot_cost("S_A12_B09_R_01") == Fraction(107)
    assert geometry.slot_cost("S_A12_B12_R_01") == Fraction(119)


def test_ground_slots_sorted_by_cost_then_slot_id(geometry: PlanningGeometry) -> None:
    order = geometry.ground_slots_by_cost()
    assert len(order) == 288
    assert order[:7] == (
        "S_A05_B01_L_01",
        "S_A05_B01_R_01",
        "S_A04_B01_L_01",
        "S_A04_B01_R_01",
        "S_A06_B01_L_01",
        "S_A06_B01_R_01",
        "S_A05_B02_L_01",
    )
    assert order[-3:] == ("S_A12_B11_R_01", "S_A12_B12_L_01", "S_A12_B12_R_01")


def test_graph_distance_never_uses_a_rack_shortcut(geometry: PlanningGeometry) -> None:
    # Neighbouring aisles, same bay: 4.5 m straight line, 2 + 4.5 + 2 by the graph.
    assert geometry.distance("N_A01_Z16", "N_A02_Z16") == Fraction(17, 2)
    assert geometry.buffer_node == "N_REL_BUFFER"
    assert geometry.home_node == "I02"


def _training(example: Assignment) -> dict[str, float]:
    skus = sorted(example.active_assignment.values())
    # DEMO_001 hottest; DEMO_002 and DEMO_003 tie and fall back to sku_id order.
    visits = {sku: float(1000 - index) for index, sku in enumerate(skus)}
    visits["DEMO_003"] = visits["DEMO_002"]
    return visits


def test_frozen_abc_assigns_hottest_skus_to_cheapest_slots(
    layout: Layout, example: Assignment, geometry: PlanningGeometry
) -> None:
    result = build_frozen_abc(layout, example, _training(example), geometry=geometry)
    slot_of = result.slot_of()
    assert slot_of["DEMO_001"] == "S_A05_B01_L_01"
    assert slot_of["DEMO_002"] == "S_A05_B01_R_01"
    assert slot_of["DEMO_003"] == "S_A04_B01_L_01"
    assert len(result.active_assignment) == 200
    assert len(result.empty_pickfaces) == 88
    assert set(result.empty_pickfaces) == set(geometry.ground_slots_by_cost()[200:])


def test_frozen_abc_keeps_reserve_lots_and_quantities(
    layout: Layout, example: Assignment, geometry: PlanningGeometry
) -> None:
    result = build_frozen_abc(layout, example, _training(example), geometry=geometry)
    before = {lot.lot_id: lot for lot in example.initial_lots}
    after = {lot.lot_id: lot for lot in result.initial_lots}
    assert before.keys() == after.keys()
    slot_of = result.slot_of()
    reserve = {s.slot_id for s in layout.slots if s.kind == "reserve"}
    for lot_id, lot in after.items():
        assert (lot.sku_id, lot.quantity) == (before[lot_id].sku_id, before[lot_id].quantity)
        if before[lot_id].slot_id in reserve:
            assert lot.slot_id == before[lot_id].slot_id
        else:
            assert lot.slot_id == slot_of[lot.sku_id]
    totals = Counter[str]()
    for lot in result.initial_lots:
        totals[lot.sku_id] += lot.quantity
    assert set(totals.values()) == {3000}
    assert result.empty_reserve_slots == example.empty_reserve_slots


def test_frozen_abc_is_deterministic_and_order_independent(
    layout: Layout, example: Assignment, geometry: PlanningGeometry
) -> None:
    visits = _training(example)
    shuffled = dict(reversed(list(visits.items())))
    first = build_frozen_abc(layout, example, visits, geometry=geometry)
    assert first == build_frozen_abc(layout, example, shuffled, geometry=geometry)
    assert first.assignment_id.startswith("frozen-abc-")


@pytest.mark.parametrize(
    "mutate",
    [
        lambda v: v.pop("DEMO_001"),
        lambda v: v.update({"DEMO_999": 1.0}),
        lambda v: v.update({"DEMO_001": -1.0}),
        lambda v: v.update({"DEMO_001": float("nan")}),
    ],
)
def test_frozen_abc_rejects_bad_visits(
    layout: Layout, example: Assignment, geometry: PlanningGeometry, mutate: object
) -> None:
    visits = _training(example)
    assert callable(mutate)
    mutate(visits)
    with pytest.raises(PlanningInputError):
        build_frozen_abc(layout, example, visits, geometry=geometry)
