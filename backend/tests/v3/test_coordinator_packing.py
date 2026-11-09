"""B2 hand timing fixed before connecting a real helper to pack/clear callbacks."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.coordinator_models import CoordinatorProfile
from tests.v3.test_coordinator_fixtures import staffing_profile
from tests.v3.test_light_flow_fixtures import hand_orders, hand_profile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor


def packing_profile(*, candidate: bool, arrival: int = 100 * SECOND) -> CoordinatorProfile:
    profile = staffing_profile()
    flow = replace(
        profile.world.receipts.flow, orders=(replace(hand_orders(1)[0], arrival_tick=arrival),)
    )
    return replace(
        profile,
        intents=profile.intents if candidate else (),
        world=replace(profile.world, receipts=replace(profile.world.receipts, flow=flow)),
    )


@pytest.mark.parametrize(
    "candidate,shipment,resource",
    [(False, 308_254_552, 313_254_552), (True, 290_170_000, 295_170_000)],
)
def test_actual_helper_pack_preserves_common_world_and_hand_completion(
    candidate: bool,
    shipment: int,
    resource: int,
) -> None:
    result = CoordinatorEngine(packing_profile(candidate=candidate), receipt_conveyor()).run(
        300 * SECOND, 400 * SECOND
    )
    assert result.status == "complete" and result.staffing_status == "valid"
    assert result.business_complete_tick == shipment
    assert result.resource_drained_tick == resource
    assert result.observation_end_tick == max(300 * SECOND, resource)
    assert result.at_end.orders[0].shipped_tick == shipment
    assert (result.at_horizon.orders[0].shipped_tick is not None) is candidate
    assert dict(result.at_end.balance.units_by_sku) == {"SKU1": 24}
    assert dict(result.at_end.balance.shipped_units_by_sku) == {"SKU1": 3}
    assert result.at_end.balance.gross_mass_kg == F("1.19")
    if candidate:
        role = next(r for r in result.at_end.roles if r.actor_id == "P12")
        assert role.restored_tick == 160 * SECOND
        pack = [
            e
            for e in result.events
            if e.kind == "operation_started"
            and e.operation is not None
            and e.operation.kind == "pack"
        ]
        assert [(e.actor_id, e.tick) for e in pack] == [("P12", 143_915_448)]
        assert (
            next(w for w in result.at_end.workers if w.actor_id == "P12").paid_ticks == 16 * SECOND
        )
    assert len(result.at_end.workers) == 24 and not result.at_end.leases


@pytest.mark.parametrize(
    "offset,actor,started", [(0, "P12", 150 * SECOND), (1, "K06", 162 * SECOND)]
)
def test_latest_helper_start_requires_complete_clear_and_paid_return(
    offset: int,
    actor: str,
    started: int,
) -> None:
    # Arrival106.084552 + deposit13 + source belt30.915448 = station150 exactly.
    profile = packing_profile(candidate=True, arrival=106_084_552 + offset)
    result = CoordinatorEngine(profile, receipt_conveyor()).run(300 * SECOND, 400 * SECOND)
    packs = [
        e
        for e in result.events
        if e.kind == "operation_started" and e.operation is not None and e.operation.kind == "pack"
    ]
    assert [(e.actor_id, e.tick) for e in packs] == [(actor, started)]
    assert next(r for r in result.at_end.roles if r.actor_id == "P12").restored_tick == 160 * SECOND
    assert result.staffing_status == "valid"


def test_two_same_hu_orders_keep_distinct_units_and_reuse_one_real_packing_actor_at_a_time() -> (
    None
):
    profile = packing_profile(candidate=True)
    flow, materials = profile.world.receipts.flow, hand_profile(orders=2)
    capacities = {o.owner_id: o.capacity for o in materials.owners}
    owners = tuple(replace(o, capacity=capacities.get(o.owner_id, o.capacity)) for o in flow.owners)
    owners += tuple(o for o in materials.owners if o.owner_id not in {v.owner_id for v in owners})
    flow = replace(
        flow,
        materials=materials.materials,
        owners=owners,
        orders=tuple(replace(o, arrival_tick=100 * SECOND) for o in hand_orders(2)),
    )
    profile = replace(
        profile, world=replace(profile.world, receipts=replace(profile.world.receipts, flow=flow))
    )
    result = CoordinatorEngine(profile, receipt_conveyor()).run(300 * SECOND, 400 * SECOND)
    assert [o.shipped_tick for o in result.at_end.orders] == [290_170_000, 321_170_000]
    assert (
        result.business_complete_tick == 321_170_000 and result.resource_drained_tick == 326_170_000
    )
    assert dict(result.at_horizon.balance.shipped_units_by_sku) == {"SKU1": 3}
    assert dict(result.at_end.balance.shipped_units_by_sku) == {"SKU1": 6}
    assert result.at_end.balance.gross_mass_kg == F("1.44")
    assert [(p.order_id, p.actor_id) for p in result.at_end.packing] == [
        ("O1", "P12"),
        ("O2", "K06"),
    ]
    assert {c.cart_id for c in result.at_end.unit_contexts} == {"CART01"}
    assert result.staffing_status == "valid" and not result.at_end.leases
