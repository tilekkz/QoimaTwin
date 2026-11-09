"""Real busy custody and concurrent receipt/whole work remain on one physical calendar."""

from dataclasses import replace

from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.staff_registry import compile_staff_registry
from tests.v3.test_coordinator_fixtures import staffing_profile
from tests.v3.test_coordinator_release import busy_picker_profile
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor, receipt_hand_profile
from tests.v3.test_staff_registry_fixtures import registry_document
from tests.v3.test_whole_flow_fixtures import whole_hand_profile


def test_request_during_paid_pick_retains_cart_exact_claim_and_original_units() -> None:
    profile = busy_picker_profile()
    document = registry_document()
    document["workers"][0]["eligible_roles"] = ["pick", "pack"]
    document["unavailability"] = [
        {"actor_id": "K05", "start_tick": 4 * SECOND, "end_tick": 100 * SECOND, "reason": "break"}
    ]
    profile = replace(
        profile,
        registry=compile_staff_registry(document),
        intents=(replace(profile.intents[0], request_tick=4 * SECOND),),
    )
    result = CoordinatorEngine(profile, receipt_conveyor()).run(5 * SECOND, 5 * SECOND)
    state = result.at_end
    assert state.roles[0].status == "quiescing" and state.roles[0].departed_tick is None
    worker = next(row for row in state.workers if row.actor_id == "P01")
    assert worker.operation is not None and worker.operation.kind == "pick"
    assert worker.operation.start_tick == 3 * SECOND
    assert worker.operation.planned_end_tick == 6 * SECOND and worker.paid_ticks == 5 * SECOND
    assert dict(state.leases)["cart"] == "O1" and state.cart.order_id == "O1"
    assert len(state.inventory.claims) == 1
    claim = state.inventory.claims[0]
    assert (claim.container_id, claim.unit_ids, claim.whole_hu) == (
        "HU1",
        ("U1", "U2", "U3"),
        False,
    )
    assert len(state.stock.locations) == 24
    assert {row.container_id for row in state.stock.locations} == {"HU1"}
    assert not state.role_bindings and result.resource_drained_tick is None
    assert not any(event.kind == "role_transition_assigned" for event in result.events)


def test_receipt_and_small_whole_shipping_share_actual_availability_and_inventory() -> None:
    profile = staffing_profile()
    receipt = receipt_hand_profile()
    world = replace(
        profile.world,
        receipts=replace(
            profile.world.receipts,
            ports=receipt.ports,
            places=receipt.places,
            receipts=receipt.receipts,
        ),
        orders=whole_hand_profile("SMALL_CARTON").orders,
    )
    document = registry_document()
    document["unavailability"].extend(
        {"actor_id": actor, "start_tick": 0, "end_tick": 20 * SECOND, "reason": "shared_break"}
        for actor in ("R01", "S01", "S02")
    )
    profile = replace(profile, world=world, registry=compile_staff_registry(document), intents=())
    result = CoordinatorEngine(profile, receipt_conveyor()).run(40 * SECOND, 80 * SECOND)
    inbound, outbound = result.at_end.receipts[0], result.at_end.whole_orders[0]
    assert (inbound.credited_tick, inbound.placed_tick, inbound.returned_tick) == (
        32 * SECOND,
        43 * SECOND,
        53 * SECOND,
    )
    assert (outbound.admitted_tick, outbound.shipped_tick, outbound.returned_tick) == (
        20 * SECOND,
        57 * SECOND,
        62 * SECOND,
    )
    assert dict(result.at_end.balance.units_by_sku) == {"SKU1": 48}
    assert dict(result.at_end.balance.shipped_units_by_sku) == {"SKU1": 24}
    assert len(result.at_end.workers) == 24 and not result.at_end.inventory.claims
    assert not result.at_end.leases and result.status == "complete"
    assert result.business_complete_tick == 57 * SECOND
    assert result.resource_drained_tick == result.observation_end_tick == 62 * SECOND
