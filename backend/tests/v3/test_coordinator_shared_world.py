"""Receipt/whole actors share actual calendar eligibility and explicit future business scope."""

from dataclasses import replace

import pytest

from app.v3.coordinator_engine import CoordinatorEngine
from app.v3.coordinator_models import CoordinatorProfile
from app.v3.staff_registry import compile_staff_registry
from tests.v3.test_coordinator_fixtures import staffing_profile
from tests.v3.test_light_flow_fixtures import hand_orders
from tests.v3.test_receipt_flow_fixtures import SECOND, receipt_conveyor, receipt_hand_profile
from tests.v3.test_staff_registry_fixtures import registry_document


def test_whole_jobs_use_same_shared_shipper_calendar_and_paid_return() -> None:
    profile = staffing_profile(whole_order=True)
    document = registry_document()
    document["unavailability"].extend(
        {"actor_id": actor, "start_tick": 0, "end_tick": 20 * SECOND, "reason": "common_break"}
        for actor in ("S01", "S02")
    )
    profile = replace(profile, registry=compile_staff_registry(document), intents=())
    outcome = CoordinatorEngine(profile, receipt_conveyor()).run(60 * SECOND, 100 * SECOND)
    job = outcome.at_end.whole_orders[0]
    assert (job.admitted_tick, job.shipped_tick, job.returned_tick) == (
        20 * SECOND,
        67 * SECOND,
        72 * SECOND,
    )
    assert outcome.business_complete_tick == 67 * SECOND
    assert outcome.resource_drained_tick == outcome.observation_end_tick == 72 * SECOND
    assert len(outcome.at_end.workers) == 24 and job.actor_id == "S01"


def receipt_profile_at(arrival: int = 0) -> CoordinatorProfile:
    profile = staffing_profile()
    receipt = receipt_hand_profile(arrival_tick=arrival)
    world_receipts = replace(
        profile.world.receipts,
        ports=receipt.ports,
        places=receipt.places,
        receipts=receipt.receipts,
    )
    return replace(profile, world=replace(profile.world, receipts=world_receipts), intents=())


def test_receipt_credit_and_paid_return_follow_shared_availability_window() -> None:
    profile = receipt_profile_at()
    document = registry_document()
    document["unavailability"].append(
        {"actor_id": "R01", "start_tick": 0, "end_tick": 20 * SECOND, "reason": "common_break"}
    )
    profile = replace(profile, registry=compile_staff_registry(document))
    outcome = CoordinatorEngine(profile, receipt_conveyor()).run(40 * SECOND, 80 * SECOND)
    receipt = outcome.at_end.receipts[0]
    assert (
        receipt.admitted_tick,
        receipt.credited_tick,
        receipt.placed_tick,
        receipt.returned_tick,
    ) == (20 * SECOND, 32 * SECOND, 43 * SECOND, 53 * SECOND)
    assert outcome.business_complete_tick == 43 * SECOND
    assert outcome.resource_drained_tick == 53 * SECOND
    assert dict(outcome.at_end.balance.units_by_sku) == {"SKU1": 48}


def test_receipt_at_horizon_is_unreleased_and_not_business_backlog() -> None:
    result = CoordinatorEngine(receipt_profile_at(40 * SECOND), receipt_conveyor()).run(
        40 * SECOND, 80 * SECOND
    )
    assert result.status == "complete" and result.business_complete_tick == 0
    assert result.at_end.receipts[0].status == "unreleased"
    assert dict(result.at_end.balance.units_by_sku) == {"SKU1": 24}


@pytest.mark.parametrize("kind", ["unit", "whole"])
def test_unit_and_whole_offers_at_horizon_are_rejected_not_silently_counted(kind: str) -> None:
    profile = staffing_profile(whole_order=kind == "whole")
    if kind == "unit":
        flow = profile.world.receipts.flow
        flow = replace(flow, orders=(replace(hand_orders(1)[0], arrival_tick=40 * SECOND),))
        world = replace(profile.world, receipts=replace(profile.world.receipts, flow=flow))
    else:
        world = replace(
            profile.world, orders=(replace(profile.world.orders[0], arrival_tick=40 * SECOND),)
        )
    engine = CoordinatorEngine(replace(profile, world=world, intents=()), receipt_conveyor())
    with pytest.raises(ValueError):
        engine.run(40 * SECOND, 80 * SECOND)
