"""Prewritten arithmetic and admission controls, not simulator-derived expectations."""

from dataclasses import replace
from fractions import Fraction as F
from typing import Any

import pytest

from app.v3.receipt_flow_models import ReceiptOffer
from app.v3.relocation_plan import plan_relocations
from app.v3.runtime_graph import DirectedGraph
from app.v3.stock_receipts import ReceiptDefinition
from tests.v3.test_relocation_plan_fixtures import hand_relocation


def test_directed_plan_retains_original_identity_and_paid_return() -> None:
    profile = hand_relocation()
    before = profile.coordinator.world.receipts.flow.stock
    (plan,) = plan_relocations(profile)
    assert [s.duration for s in plan.steps] == [
        2_000_000,
        2_000_000,
        3_000_000,
        1_000_000,
        5_000_000,
    ]
    assert sum(s.duration for s in plan.steps) == 13_000_000
    assert [s.kind for s in plan.steps] == [
        "relocation_approach",
        "relocation_take",
        "relocation_carry",
        "relocation_place",
        "relocation_return",
    ]
    assert plan.unit_ids == tuple(f"U{i}" for i in range(1, 25))
    assert (plan.sku_id, plan.lot_id, plan.gross_mass_kg) == ("SKU1", "LOT1", F(47, 50))
    assert profile.coordinator.world.receipts.flow.stock == before


def test_empty_jobs_preserve_noop_without_stock_mutation() -> None:
    assert plan_relocations(replace(hand_relocation(), jobs=())) == ()


@pytest.mark.parametrize(
    "field,value",
    [("arrival_tick", True), ("take_ticks", 0), ("place_ticks", F(1)), ("arrival_tick", -1)],
)
def test_job_ticks_require_exact_nonnegative_integers(field: str, value: Any) -> None:
    profile = hand_relocation()
    with pytest.raises(ValueError):
        plan_relocations(replace(profile, jobs=(replace(profile.jobs[0], **{field: value}),)))


@pytest.mark.parametrize("permission", [(), ("P01",), ("S01", "S01")])
def test_explicit_existing_shipper_permission_is_required(permission: tuple[str, ...]) -> None:
    with pytest.raises(ValueError):
        plan_relocations(replace(hand_relocation(), permitted_actor_ids=permission))


def test_two_jobs_and_same_source_destination_are_rejected() -> None:
    profile = hand_relocation()
    with pytest.raises(ValueError):
        plan_relocations(replace(profile, jobs=profile.jobs * 2))
    with pytest.raises(ValueError):
        plan_relocations(replace(profile, jobs=(replace(profile.jobs[0], to_slot_id="slot"),)))


def test_claimed_work_identity_cannot_alias_a_role_intent() -> None:
    profile = hand_relocation()
    with pytest.raises(ValueError):
        plan_relocations(replace(profile, jobs=(replace(profile.jobs[0], job_id="I11"),)))


def test_missing_directed_loaded_permission_is_not_a_reverse_fallback() -> None:
    profile = hand_relocation()
    flow = profile.coordinator.world.receipts.flow
    arcs = tuple(
        replace(a, cargo_classes=frozenset()) if a.arc_id == "b" else a for a in flow.graph.arcs
    )
    graph = DirectedGraph("denied", flow.graph.node_ids, arcs)
    flow = replace(flow, graph=graph)
    common = replace(
        profile.coordinator,
        world=replace(
            profile.coordinator.world,
            receipts=replace(profile.coordinator.world.receipts, flow=flow),
        ),
    )
    with pytest.raises(ValueError, match="route"):
        plan_relocations(replace(profile, coordinator=common))


def test_integer_speed_alias_rejects_before_building_routes() -> None:
    profile = hand_relocation()
    flow = profile.coordinator.world.receipts.flow
    actors = tuple(replace(a, speed_m_s=1) if a.actor_id == "S01" else a for a in flow.actors)  # type: ignore[arg-type]
    flow = replace(flow, actors=actors)
    common = replace(
        profile.coordinator,
        world=replace(
            profile.coordinator.world,
            receipts=replace(profile.coordinator.world.receipts, flow=flow),
        ),
    )
    with pytest.raises(ValueError):
        plan_relocations(replace(profile, coordinator=common))


def test_target_module_mass_limit_is_not_replaced_by_slot_rating() -> None:
    profile = hand_relocation()
    places = (profile.places[0], replace(profile.places[1], module_max_gross_kg=F(9, 10)))
    with pytest.raises(ValueError, match="module"):
        plan_relocations(replace(profile, places=places))


def test_same_module_move_counts_the_original_hu_once() -> None:
    profile = hand_relocation()
    places = tuple(
        replace(p, module_id="SAME", module_max_gross_kg=F(1), module_max_hus=1)
        for p in profile.places
    )
    assert len(plan_relocations(replace(profile, places=places))) == 1


@pytest.mark.parametrize("mass_limit,hu_limit", [(F(3, 2), 2), (F(2), 1)])
def test_promised_receipt_competes_for_module_mass_and_count(mass_limit: F, hu_limit: int) -> None:
    profile = hand_relocation()
    target = replace(profile.places[1], module_max_gross_kg=mass_limit, module_max_hus=hu_limit)
    future = replace(target, owner_id="future", node_id="DEST")
    definition = ReceiptDefinition("ARRIVAL", "FUTURE-HU", "SKU1", "future-lot", 24)
    receipt = ReceiptOffer(definition, 0, "IN", "future")
    common = profile.coordinator
    world = replace(common.world, receipts=replace(common.world.receipts, receipts=(receipt,)))
    profile = replace(
        profile,
        coordinator=replace(common, world=world),
        places=(profile.places[0], target, future),
    )
    with pytest.raises(ValueError, match="module"):
        plan_relocations(profile)


def test_actor_payload_limit_can_be_lower_than_the_manual_ceiling() -> None:
    profile = hand_relocation()
    common = profile.coordinator
    flow = common.world.receipts.flow
    actors = tuple(
        replace(a, max_gross_kg=F(9, 10)) if a.actor_id == "S01" else a for a in flow.actors
    )
    world = replace(
        common.world, receipts=replace(common.world.receipts, flow=replace(flow, actors=actors))
    )
    with pytest.raises(ValueError, match="actor mass"):
        plan_relocations(replace(profile, coordinator=replace(common, world=world)))
