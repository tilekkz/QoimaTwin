"""Applying a plan and its before-shift relocation records (05 §9 P2, P5)."""

from __future__ import annotations

from fractions import Fraction
from itertools import pairwise

import pytest

from app.contracts.config import SimulationConfig
from app.contracts.layout import Layout
from app.planning import (
    PlanArtifact,
    PlanningInputError,
    TransferRecord,
    apply_plan,
    assignment_hash,
    plan_swaps,
    verify_plan,
)
from app.planning.apply import plan_content_hash, replay_transfers
from tests.planning_support import CHEAP, DEAR, RESERVE_SLOT, two_sku_inputs

TPS = 3_000_000


@pytest.fixture(scope="module")
def swap_plan(layout: Layout, config: SimulationConfig) -> PlanArtifact:
    inputs = two_sku_inputs(layout, config, expected={"SKU_X": 0.0, "SKU_Y": 10.0})
    return plan_swaps(inputs, budget=2)


def test_p2_one_swap_has_three_transfers_and_six_handlings(swap_plan: PlanArtifact) -> None:
    transfers = swap_plan.relocation.transfers
    assert [(t.lot_id, t.from_location, t.to_location) for t in transfers] == [
        ("GROUND_SKU_X", CHEAP, "N_REL_BUFFER"),
        ("GROUND_SKU_Y", DEAR, CHEAP),
        ("GROUND_SKU_X", "N_REL_BUFFER", DEAR),
    ]
    assert all(t.quantity == 2000 for t in transfers)
    handling = [a for a in swap_plan.relocation.actions if a.state == "BUSY_SERVICE"]
    assert [a.operation for a in handling] == ["relocation_take", "relocation_place"] * 3
    assert all(a.end_tick - a.start_tick == 8 * TPS for a in handling)


def test_relocation_timeline_matches_route_arithmetic(swap_plan: PlanArtifact) -> None:
    schedule = swap_plan.relocation
    assert schedule.shift_start_s == 0
    assert schedule.window_s == 328
    actions = schedule.actions
    assert actions[0].start_s == 0
    assert actions[-1].end_s == 328
    assert all(a.end_s > a.start_s for a in actions)
    assert all(b.start_s == a.end_s for a, b in pairwise(actions))
    # I02 -> N_A01_Z16 is 22 m at 1.2 m/s = 55/3 s; the first take ends 8 s later.
    first_take = schedule.transfers[0]
    assert first_take.take_end_tick == (Fraction(55, 3) + 8) * TPS
    travel = [a for a in actions if a.state == "TRAVEL"]
    assert travel[0].node_ids[0] == "I02" and travel[-1].node_ids[-1] == "I02"
    assert schedule.ticks_per_second == TPS


def test_apply_plan_moves_whole_lots_and_keeps_reserve(
    swap_plan: PlanArtifact, layout: Layout, config: SimulationConfig
) -> None:
    baseline = two_sku_inputs(layout, config, expected={"SKU_X": 0, "SKU_Y": 1}).baseline_assignment
    result = apply_plan(baseline, swap_plan, layout)
    assert result == swap_plan.final_assignment
    lots = {lot.lot_id: lot for lot in result.initial_lots}
    assert (lots["GROUND_SKU_X"].slot_id, lots["GROUND_SKU_X"].quantity) == (DEAR, 2000)
    assert (lots["GROUND_SKU_Y"].slot_id, lots["GROUND_SKU_Y"].quantity) == (CHEAP, 2000)
    assert lots["RESERVE_1"].slot_id == RESERVE_SLOT
    assert len(result.initial_lots) == len(baseline.initial_lots)
    assert assignment_hash(result) == swap_plan.final_assignment_hash
    assert assignment_hash(baseline) == swap_plan.baseline_assignment_hash


def test_apply_rejects_a_different_baseline(
    swap_plan: PlanArtifact, layout: Layout, config: SimulationConfig
) -> None:
    other = two_sku_inputs(layout, config, expected={"SKU_X": 0, "SKU_Y": 1}, hot_on_dear=False)
    with pytest.raises(PlanningInputError, match="baseline"):
        apply_plan(other.baseline_assignment, swap_plan, layout)


def test_noop_apply_returns_the_same_assignment(layout: Layout, config: SimulationConfig) -> None:
    inputs = two_sku_inputs(layout, config, expected={"SKU_X": 0.0, "SKU_Y": 10.0})
    plan = plan_swaps(inputs, budget=0)
    assert apply_plan(inputs.baseline_assignment, plan, layout) == inputs.baseline_assignment


def _tamper_route(plan: PlanArtifact) -> PlanArtifact:
    """Replace the B->A walk by a straight hop between two service nodes (a rack shortcut)."""
    actions = list(plan.relocation.actions)
    index = next(
        i
        for i, a in enumerate(actions)
        if a.state == "TRAVEL" and a.node_ids[0] == "N_A12_Z34" and a.node_ids[-1] == "N_A01_Z16"
    )
    actions[index] = actions[index].model_copy(update={"node_ids": ("N_A12_Z34", "N_A01_Z16")})
    relocation = plan.relocation.model_copy(update={"actions": tuple(actions)})
    return plan.model_copy(update={"relocation": relocation})


def test_p5_plan_with_rack_shortcut_is_rejected(swap_plan: PlanArtifact, layout: Layout) -> None:
    verify_plan(swap_plan, layout)
    with pytest.raises(PlanningInputError, match="edge"):
        verify_plan(_tamper_route(swap_plan), layout)


def test_p5_plan_with_understated_distance_is_rejected(
    swap_plan: PlanArtifact, layout: Layout
) -> None:
    pair = swap_plan.selected_pairs[0]
    cheaper = pair.model_copy(update={"route_distance_m": 300.0})
    tampered = swap_plan.model_copy(update={"selected_pairs": (cheaper,)})
    with pytest.raises(PlanningInputError, match="distance"):
        verify_plan(tampered, layout)


def test_tampered_plan_fails_its_hash(swap_plan: PlanArtifact, layout: Layout) -> None:
    tampered = swap_plan.model_copy(update={"forecast_id": "edited"})
    with pytest.raises(PlanningInputError, match="plan_id"):
        verify_plan(tampered, layout)


def test_plan_json_round_trip(swap_plan: PlanArtifact, layout: Layout) -> None:
    text = swap_plan.model_dump_json(by_alias=True)
    again = PlanArtifact.model_validate_json(text)
    assert again == swap_plan
    verify_plan(again, layout)


def _transfers(plan: PlanArtifact, **changes: object) -> list[TransferRecord]:
    records = list(plan.relocation.transfers)
    records[1] = records[1].model_copy(update=changes)
    return records


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"lot_id": "GROUND_SKU_X"}, "not at the source"),
        ({"quantity": 1999}, "not at the source"),
        ({"to_location": "N_REL_BUFFER"}, "occupied"),
    ],
)
def test_replay_rejects_created_split_or_doubled_lots(
    swap_plan: PlanArtifact,
    layout: Layout,
    config: SimulationConfig,
    changes: dict[str, object],
    message: str,
) -> None:
    baseline = two_sku_inputs(layout, config, expected={"SKU_X": 0, "SKU_Y": 1}).baseline_assignment
    with pytest.raises(PlanningInputError, match=message):
        replay_transfers(baseline, _transfers(swap_plan, **changes), "N_REL_BUFFER", "x")


def test_replay_rejects_a_lot_left_in_the_buffer(
    swap_plan: PlanArtifact, layout: Layout, config: SimulationConfig
) -> None:
    baseline = two_sku_inputs(layout, config, expected={"SKU_X": 0, "SKU_Y": 1}).baseline_assignment
    with pytest.raises(PlanningInputError, match="empty buffer"):
        replay_transfers(baseline, swap_plan.relocation.transfers[:1], "N_REL_BUFFER", "x")


def _rehashed(plan: PlanArtifact, **changes: object) -> PlanArtifact:
    """An edited plan whose plan_id was recomputed, so only content checks can catch it."""
    edited = plan.model_copy(update=changes)
    return edited.model_copy(update={"plan_id": plan_content_hash(edited)})


def test_rehashed_plan_with_unpaid_relocation_is_rejected(
    swap_plan: PlanArtifact, layout: Layout
) -> None:
    free = _rehashed(swap_plan, relocation_labor_ticks=0, relocation_labor_s=0.0)
    with pytest.raises(PlanningInputError, match="totals"):
        verify_plan(free, layout)


def test_rehashed_plan_with_foreign_sku_is_rejected(
    swap_plan: PlanArtifact, layout: Layout
) -> None:
    pair = swap_plan.selected_pairs[0].model_copy(update={"sku_a": "ZZZ"})
    with pytest.raises(PlanningInputError, match="shortlist"):
        verify_plan(_rehashed(swap_plan, selected_pairs=(pair,)), layout)


def test_rehashed_plan_with_short_handling_is_rejected(
    swap_plan: PlanArtifact, layout: Layout
) -> None:
    actions = list(swap_plan.relocation.actions)
    take = next(i for i, a in enumerate(actions) if a.state == "BUSY_SERVICE")
    actions[take] = actions[take].model_copy(update={"end_tick": actions[take].end_tick - 1})
    schedule = swap_plan.relocation.model_copy(update={"actions": tuple(actions)})
    with pytest.raises(PlanningInputError, match="schedule"):
        verify_plan(_rehashed(swap_plan, relocation=schedule), layout)
